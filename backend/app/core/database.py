import warnings
from collections.abc import Iterator

from sqlalchemy import Column, Integer, MetaData, Sequence, String, Table, create_engine, event, inspect, select, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

IS_SQLITE = get_settings().database_url.startswith("sqlite")

if IS_SQLITE:
    # Demo mode stores money as REAL; reads are rounded back to 2 places. PostgreSQL (the default) has exact NUMERIC.
    warnings.filterwarnings("ignore", message=".*does \\*not\\* support Decimal objects natively.*")
    engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _sqlite_connect(dbapi_connection, _):
        # Recipe from the SQLAlchemy docs: take over transaction control so SAVEPOINTs and rollbacks behave.
        dbapi_connection.isolation_level = None
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")  # API + worker + scheduler write concurrently
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    @event.listens_for(engine, "begin")
    def _sqlite_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")  # take the write lock up front: concurrent writers queue (busy_timeout) instead of failing mid-transaction
else:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Human-readable numbers (INV-000042). PostgreSQL uses real sequences (see migrations); SQLite uses this counter table.
_counters = Table("number_counters", MetaData(), Column("name", String(50), primary_key=True), Column("value", Integer, nullable=False, default=0))


def init_sqlite_schema() -> None:
    """SQLite demo mode has no Alembic: create every table straight from the models."""
    import app.models.registry  # noqa: F401  (registers all tables)

    Base.metadata.create_all(engine)
    _counters.create(engine, checkfirst=True)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """create_all never alters existing tables; add columns introduced after a demo DB file was created."""
    with engine.begin() as conn:
        insp = inspect(conn)  # same connection: a second one would deadlock on SQLite's write lock
        for table in Base.metadata.sorted_tables:
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)}'
                default = col.server_default.arg if col.server_default is not None else None
                if default is not None:
                    lit = getattr(default, "text", default) if not isinstance(default, str) else default
                    lit = lit if isinstance(lit, str) else "0"  # bool/int server defaults (sa.false() etc.)
                    ddl += f" DEFAULT {lit if lit[:1] == chr(39) or lit.lstrip('-').replace('.', '', 1).isdigit() else repr(lit)}"
                conn.exec_driver_sql(ddl)


def get_db() -> Iterator[Session]:
    """One session per request; commit/rollback is the service layer's job."""
    with SessionLocal() as db:
        yield db


def next_number(db: Session, sequence: str, prefix: str, width: int = 6) -> str:
    """Gap-tolerant unique numbers, e.g. INV-000042 (PostgreSQL sequence, or an atomic counter row on SQLite)."""
    if IS_SQLITE:
        if db.execute(update(_counters).where(_counters.c.name == sequence).values(value=_counters.c.value + 1)).rowcount == 0:
            db.execute(_counters.insert().values(name=sequence, value=1))  # first use; the write lock held since UPDATE serialises writers
        n = db.scalar(select(_counters.c.value).where(_counters.c.name == sequence))
    else:
        n = db.scalar(select(Sequence(sequence).next_value()))
    return f"{prefix}-{n:0{width}d}"
