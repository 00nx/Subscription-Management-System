#!/usr/bin/env python3
"""Run Brightloop with no database server (Windows, macOS, Linux).

    python dev.py              set everything up (first run) and start the app        <- the default
    python dev.py setup        install dependencies, create the database, load demo data - then stop
    python dev.py seed         (re)load demo data (safe to repeat)
    python dev.py razorpay     check the Razorpay Test Mode setup step by step (run while the app is running)
    python dev.py --postgres   use a PostgreSQL 16 server instead of SQLite (recommended for real billing)
    python dev.py --no-ngrok   do not start the ngrok tunnel (by default it starts when ngrok is installed)

ngrok (optional): if `ngrok` is on your PATH it is started for the API (port 8000) so Razorpay can reach the webhook; the launcher then prints
the public webhook URL. One-time setup: install ngrok and run `ngrok config add-authtoken <token>`. Without ngrok everything else still works.

You need: Python 3.12+ and Node.js 20+ with npm. That is all: the data lives in ONE SQLite file (brightloop-demo.db; delete it to reset).
Redis is OPTIONAL: without it everything works except the background worker/scheduler (use Billing > "Run billing now").
--postgres also needs a PostgreSQL 16 server. DATABASE_URL / REDIS_URL env vars override backend/.env.
PGSUPERPASSWORD = password of the PostgreSQL 'postgres' user (only used once with --postgres, to create the app's role; asked if not set).
"""
import argparse
import getpass
import hashlib
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND, FRONTEND, LOGS = ROOT / "backend", ROOT / "frontend", ROOT / "logs"
IS_WIN = os.name == "nt"
SQLITE = True  # the default; --postgres turns it off
SQLITE_FILE = ROOT / "brightloop-demo.db"
VENV = BACKEND / ".venv"
PY = str(VENV / ("Scripts/python.exe" if IS_WIN else "bin/python"))
DEFAULT_DB_URL = "postgresql+psycopg://brightloop:brightloop_dev@localhost:5432/brightloop"
API = "http://localhost:8000/api/v1"


def say(msg: str) -> None:
    print(f"[dev] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"\n[ERROR] {msg}\n", flush=True)
    sys.exit(1)


def run(cmd, cwd=None, env=None, check=True) -> int:
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, env={**os.environ, **(env or {})})
    if check and r.returncode:
        die(f"Command failed ({r.returncode}): {' '.join(str(c) for c in cmd)}")
    return r.returncode


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- prerequisites & files
def check_tools() -> str:
    if sys.version_info < (3, 12):
        die(f"Python 3.12+ is required (this is {sys.version.split()[0]}). Install it from https://www.python.org/downloads/")
    npm = shutil.which("npm")
    if not npm or not shutil.which("node"):
        die("Node.js 20+ (with npm) is required. Install it from https://nodejs.org/")
    return npm


def ensure_venv() -> None:
    if not Path(PY).exists():
        say("Creating Python virtual environment (backend/.venv)...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    req = BACKEND / "requirements.txt"
    marker = VENV / ".requirements-hash"
    digest = hashlib.sha256(req.read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text() != digest:
        say("Installing backend dependencies (first run takes a minute)...")
        run([PY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", req])
        marker.write_text(digest)


def ensure_frontend_deps(npm: str) -> None:
    if not (FRONTEND / "node_modules").exists():
        say("Installing frontend dependencies (npm ci)...")
        run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND)


def ensure_env_files() -> None:
    be = BACKEND / ".env"
    if not be.exists():
        say("Creating backend/.env with a generated SECRET_KEY...")
        be.write_text(
            f"ENVIRONMENT=development\nSECRET_KEY={secrets.token_hex(32)}\nREDIS_URL=redis://localhost:6379/0\n"
            'CORS_ORIGINS=["http://localhost:5173"]\nCOOKIE_SECURE=false\nFRONTEND_URL=http://localhost:5173\n'
            "\n# Razorpay TEST MODE only (rzp_test_ keys). See docs/RAZORPAY.md. Restart the app after editing.\n"
            "RAZORPAY_KEY_ID=\nRAZORPAY_KEY_SECRET=\nRAZORPAY_WEBHOOK_SECRET=\n", encoding="utf-8")
    else:  # an older backend/.env: add any Razorpay keys it lacks (blank, never overwriting what is there)
        text = be.read_text(encoding="utf-8")
        missing = [k for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET") if not any(l.strip().startswith(k + "=") for l in text.splitlines())]
        if missing:
            say("Adding blank Razorpay settings to backend/.env (fill them in, then restart).")
            be.write_text(text.rstrip("\n") + "\n\n# Razorpay TEST MODE only (rzp_test_ keys). See docs/RAZORPAY.md. Restart the app after editing.\n" + "".join(f"{k}=\n" for k in missing), encoding="utf-8")
    fe = FRONTEND / ".env"
    if not fe.exists():
        fe.write_text("VITE_API_URL=http://localhost:8000/api/v1\n", encoding="utf-8")


def settings() -> dict[str, str]:
    if SQLITE:
        return {"DATABASE_URL": f"sqlite:///{SQLITE_FILE.as_posix()}", "REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0")}
    file_env = read_env(BACKEND / ".env")
    pg_file = file_env.get("DATABASE_URL", "")
    return {"DATABASE_URL": os.environ.get("DATABASE_URL", pg_file if pg_file.startswith("postgresql") else DEFAULT_DB_URL),
            "REDIS_URL": os.environ.get("REDIS_URL", file_env.get("REDIS_URL", "redis://localhost:6379/0"))}


# ---------------------------------------------------------------- database
def _plain(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


CONNECT = "import sys, psycopg; psycopg.connect(sys.argv[1], connect_timeout=5).close()"
CREATE = """
import sys, psycopg
from psycopg import sql
su_url, user, pw, *dbs = sys.argv[1:]
with psycopg.connect(su_url, autocommit=True, connect_timeout=5) as c:
    q = "ALTER ROLE {} WITH LOGIN PASSWORD {} CREATEDB" if c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (user,)).fetchone() else "CREATE ROLE {} LOGIN PASSWORD {} CREATEDB"
    c.execute(sql.SQL(q).format(sql.Identifier(user), sql.Literal(pw)))
    for db in dbs:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,)).fetchone():
            c.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(db), sql.Identifier(user)))
"""


def ensure_database() -> None:
    url = settings()["DATABASE_URL"]
    u = urllib.parse.urlparse(url)
    host, port = u.hostname or "localhost", u.port or 5432
    dbs = [u.path.lstrip("/")]
    ok = lambda target: subprocess.run([PY, "-c", CONNECT, _plain(target)], capture_output=True).returncode == 0  # noqa: E731
    if ok(url):
        return
    if not port_open(host, port):
        die(f"PostgreSQL is not running on {host}:{port}.\n"
            "  Install PostgreSQL 16 (https://www.postgresql.org/download/windows/ - keep the default port 5432 and remember the\n"
            "  password you set for the 'postgres' user), make sure the service is started, then run this again.")
    say(f"Creating the database role '{u.username}' and database {dbs} (needs the PostgreSQL 'postgres' user's password)...")
    pw = os.environ.get("PGSUPERPASSWORD") or getpass.getpass("Password of the PostgreSQL 'postgres' user: ")
    su = f"postgresql://postgres:{urllib.parse.quote(pw, safe='')}@{host}:{port}/postgres"
    r = subprocess.run([PY, "-c", CREATE, su, u.username or "brightloop", urllib.parse.unquote(u.password or ""), *dbs], capture_output=True, text=True)
    if r.returncode:
        die("Could not create the database with that password:\n  " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])
    if not ok(url):
        die("The database was created but the app could not log in with DATABASE_URL from backend/.env. Check that URL.")


def migrate_and_seed() -> None:
    if SQLITE:
        say(f"Creating the SQLite database ({SQLITE_FILE.name})...")
        run([PY, "-m", "app.sqlite_init"], cwd=BACKEND, env=settings())
    else:
        say("Applying database migrations...")
        run([PY, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=settings())
    say("Loading demo data (skipped if already present)...")
    run([PY, "-m", "app.seed"], cwd=BACKEND, env=settings())


def prepare() -> str:
    npm = check_tools()
    ensure_venv()
    ensure_env_files()
    if not SQLITE:
        ensure_database()
    ensure_frontend_deps(npm)
    return npm


# ---------------------------------------------------------------- run
def stop(procs: list[tuple[str, subprocess.Popen]]) -> None:
    for name, p in procs:
        if p.poll() is None:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    time.sleep(1)
    for name, p in procs:
        if p.poll() is None and not IS_WIN:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def spawn(name: str, cmd, cwd: Path, procs: list) -> None:
    LOGS.mkdir(exist_ok=True)
    log = open(LOGS / f"{name}.log", "w", encoding="utf-8")
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WIN else {"start_new_session": True}
    procs.append((name, subprocess.Popen([str(c) for c in cmd], cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, **settings()}, **kw)))
    say(f"started {name}  (log: logs/{name}.log)")


def log_tail(name: str, lines: int = 25) -> str:
    try:
        return "\n".join((LOGS / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log yet)"


def api_up() -> bool:
    """Is the API answering? Probes /openapi.json, which touches neither the database nor Redis (the health endpoint pings
    Redis, and an absent Redis refuses slowly on Windows, so it is a bad readiness probe). Falls back to uvicorn's own
    'running' line in the log plus an open port, so a slow HTTP answer can never make us kill a healthy API."""
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/openapi.json", timeout=5)
        return True
    except urllib.error.HTTPError:
        return True  # it answered
    except OSError:
        pass
    return "Uvicorn running on" in log_tail("api", 60) and port_open("127.0.0.1", 8000)


def check_ports() -> None:
    for port, what in ((8000, "the API"), (5173, "the web app")):
        if port_open("127.0.0.1", port):
            die(f"Port {port} ({what}) is already in use by another program, possibly an earlier Brightloop window that is still running.\n"
                f"  Close that window, or find and stop the program:\n"
                f"    Windows:      netstat -ano | findstr :{port}      then      taskkill /PID <number> /F\n"
                f"    macOS/Linux:  lsof -i :{port}                      then      kill <pid>")


NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def ngrok_public_url() -> str | None:
    """The https URL of a running ngrok tunnel to port 8000 (ours, or one already started by hand), else None."""
    try:
        with urllib.request.urlopen(NGROK_API, timeout=2) as r:
            import json
            tunnels = json.load(r).get("tunnels", [])
    except (OSError, ValueError):
        return None
    for t in tunnels:
        if str(t.get("config", {}).get("addr", "")).rstrip("/").endswith(":8000") and str(t.get("public_url", "")).startswith("https://"):
            return t["public_url"]
    return None


def razorpay_status() -> str:
    """One line for the startup banner: is Razorpay Test Mode usable? (values are never printed)"""
    env = {**read_env(BACKEND / ".env"), **{k: v for k, v in os.environ.items() if k.startswith("RAZORPAY_")}}
    kid, sec, wh = (env.get(k, "").strip() for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"))
    if not kid and not sec:
        return "Razorpay: not configured (optional). Add your rzp_test_ keys to backend/.env, then restart. Check: run.cmd razorpay"
    if not kid.startswith("rzp_test_"):
        return "Razorpay: PROBLEM - RAZORPAY_KEY_ID is not a Test Mode key (it must start with rzp_test_; a LIVE key is refused and webhooks answer 503). In the Razorpay dashboard switch to Test Mode, generate a key there, put it in backend/.env and restart."
    if not sec:
        return "Razorpay: PROBLEM - RAZORPAY_KEY_SECRET is empty in backend/.env."
    if not wh or wh.startswith("http"):
        return "Razorpay: PROBLEM - RAZORPAY_WEBHOOK_SECRET " + ("is empty" if not wh else "is a URL; it must be a random string you invent (the same one you type in the dashboard)") + " in backend/.env."
    return "Razorpay: ready (Test Mode keys found). Check everything with: run.cmd razorpay"


def start_ngrok(extra: list) -> str | None:
    """Starts `ngrok http 8000` if it is installed and no tunnel exists yet. Never fatal: the app works without it. Returns the public URL."""
    if (url := ngrok_public_url()):
        say("ngrok already running: reusing its tunnel.")
        return url
    exe = shutil.which("ngrok")
    if not exe:
        say("ngrok not found: skipping the tunnel (only needed for Razorpay webhooks). Install it from https://ngrok.com/download, then run `ngrok config add-authtoken <token>` once.")
        return None
    spawn("ngrok", [exe, "http", "127.0.0.1:8000", "--log=stdout"], ROOT, extra)  # 127.0.0.1, not "localhost": avoids ngrok reaching a different listener over IPv6
    proc = extra[-1][1]
    deadline = time.time() + 20
    while time.time() < deadline:
        if (url := ngrok_public_url()):
            return url
        if proc.poll() is not None:
            break
        time.sleep(1)
    say("ngrok did not start a tunnel (the app keeps running). Last lines of logs/ngrok.log:\n\n" + log_tail("ngrok", 8)
        + "\n\nCommon cause: no authtoken yet. Run `ngrok config add-authtoken <token>` (token: dashboard.ngrok.com/get-started/your-authtoken). "
        "If ngrok is already open in another window, close that one.")
    return None


def start(npm: str, use_ngrok: bool = True) -> None:
    check_ports()
    migrate_and_seed()
    procs: list[tuple[str, subprocess.Popen]] = []
    extra: list[tuple[str, subprocess.Popen]] = []  # helpers whose death must not stop the app (ngrok)
    ru = urllib.parse.urlparse(settings()["REDIS_URL"])
    redis_ok = port_open(ru.hostname or "localhost", ru.port or 6379)
    try:
        spawn("api", [PY, "-m", "uvicorn", "app.main:app", "--port", "8000"], BACKEND, procs)
        if redis_ok:
            pool = ["-P", "solo"] if IS_WIN else []  # Celery's default prefork pool does not work on Windows
            spawn("worker", [PY, "-m", "celery", "-A", "app.tasks.celery_app", "worker", "-l", "info", *pool], BACKEND, procs)
            spawn("beat", [PY, "-m", "celery", "-A", "app.tasks.celery_app", "beat", "-l", "info", "--schedule", str(LOGS / "celerybeat-schedule")], BACKEND, procs)
        else:
            say("Redis not found: running WITHOUT the background worker/scheduler. Everything else works; use Billing > 'Run billing now'.")
        spawn("frontend", [npm, "run", "dev", "--", "--strictPort"], FRONTEND, procs)  # fail rather than silently move to another port (CORS expects 5173)
        say("Waiting for the API (the first start can take a minute: Windows security software scans new files)...")
        deadline = time.time() + 150
        last_dot = 0.0
        while not api_up():
            if procs[0][1].poll() is not None:
                die(f"The API stopped while starting. This is its log (logs/api.log):\n\n{log_tail('api')}")
            if time.time() > deadline:
                die(f"The API did not answer on http://localhost:8000 within 150 s. Last lines of logs/api.log:\n\n{log_tail('api')}")
            if time.time() - last_dot > 10:
                print("  ... still starting", flush=True)
                last_dot = time.time()
            time.sleep(1)
        tunnel = start_ngrok(extra) if use_ngrok else None
        print("""
=================================================================
  Brightloop is running
    App ............ http://localhost:5173
    API docs ....... http://localhost:8000/docs
  Demo logins (development data only):
    admin@brightloop.dev   / Admin@12345
    staff1@brightloop.dev  / Staff@12345
    alice@example.com      / Customer@12345
  Logs are in the logs/ folder.  Press Ctrl+C here to stop everything.
=================================================================
  """ + razorpay_status() + """
""" + (f"""  Razorpay webhook URL (paste into Razorpay Dashboard > Settings > Webhooks, Test Mode):
    {tunnel}/api/v1/webhooks/razorpay/
  Secret = RAZORPAY_WEBHOOK_SECRET from backend/.env. Events: payment.captured, payment.failed, order.paid.
  ngrok inspector: http://127.0.0.1:4040   (the free URL changes every time ngrok restarts)
""" if tunnel else "") + ("""  Data: brightloop-demo.db (SQLite). Delete it to start over. For real billing use `python dev.py --postgres`
  (exact decimal money and row-level locking).
""" if SQLITE else ""), flush=True)
        while all(p.poll() is None for _, p in procs):
            time.sleep(1)
        dead = [n for n, p in procs if p.poll() is not None]
        say(f"{', '.join(dead)} stopped unexpectedly. Last lines of logs/{dead[0]}.log:\n\n{log_tail(dead[0])}")
    except KeyboardInterrupt:
        say("Stopping...")
    finally:
        stop(procs + extra)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Brightloop")
    ap.add_argument("command", nargs="?", default="start", choices=["start", "setup", "seed", "razorpay"])
    ap.add_argument("--postgres", action="store_true", help="use a PostgreSQL 16 server instead of the default SQLite file")
    ap.add_argument("--sqlite", action="store_true", help="(default, kept for compatibility)")
    ap.add_argument("--no-ngrok", action="store_true", help="do not start the ngrok tunnel")
    args = ap.parse_args()
    cmd = args.command
    global SQLITE
    SQLITE = not args.postgres
    npm = prepare()
    if cmd == "setup":
        migrate_and_seed()
        say("Setup complete. Start the app with:  python dev.py")
    elif cmd == "seed":
        migrate_and_seed()
    elif cmd == "razorpay":
        sys.exit(run([PY, "-m", "scripts.razorpay_check"], cwd=BACKEND, check=False))
    else:
        start(npm, use_ngrok=not args.no_ngrok)


if __name__ == "__main__":
    main()
