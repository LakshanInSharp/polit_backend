import logging
import os
from email.message import EmailMessage

import aiosmtplib
from dotenv import load_dotenv

load_dotenv()  
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASSWORD")


if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
    raise RuntimeError(
        "Missing SMTP config: set SMTP_HOST, SMTP_USER and SMTP_PASS in .env"
    )


logger = logging.getLogger("email_utils")
logging.basicConfig(level=logging.DEBUG)

async def send_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text email via SMTP. Logs successes and failures.
    """
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"]   = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        logger.debug(f"Connecting to SMTP {SMTP_HOST}:{SMTP_PORT} as {SMTP_USER}")
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASS,
        )
        logger.info(f"Email sent to {to!r}")
    except Exception as e:
        logger.error(f"Failed to send email to {to!r}: {e}", exc_info=True)
        raise