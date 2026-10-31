import smtplib
from email.message import EmailMessage
from app.config import settings


def send_email(subject: str, message: str, recipients: list[str]) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(message)

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        settings.EMAIL_PORT
    ) as smtp:
        smtp.login(
            settings.EMAIL_HOST_USER,
            settings.EMAIL_HOST_PASSWORD
        )
        smtp.send_message(msg)