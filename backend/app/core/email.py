import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    """SMTP when SMTP_HOST is set, otherwise the console/log backend (development). Raises on failure: callers record it."""
    s = get_settings()
    if not s.smtp_host:
        log.info("EMAIL (console backend) to=%s subject=%s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.email_from, to, subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)
