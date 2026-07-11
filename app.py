"""
Portfolio backend — handles the contact form.

Receives {name, email, message} from the React frontend and emails it to
the site owner via SMTP. Configure credentials in a .env file (see
.env.example) — never commit real credentials.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

# Resolve the configuration next to this file, so the API works whether it is
# launched from the repository root or from the backend directory.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
TO_EMAIL = os.getenv("TO_EMAIL", SMTP_USER)
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="Portfolio Contact API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class ContactMessage(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    message: str = Field(min_length=1, max_length=5000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def deliver_contact_email(payload: ContactMessage):
    if not SMTP_USER or not SMTP_PASS:
        raise HTTPException(
            status_code=500,
            detail="Email is not configured on the server. Set SMTP_USER / SMTP_PASS in .env",
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Portfolio contact from {payload.name}"
    msg["From"] = SMTP_USER
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = payload.email

    body = (
        f"New message from your portfolio site\n\n"
        f"Name: {payload.name}\n"
        f"Email: {payload.email}\n\n"
        f"Message:\n{payload.message}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        tls_context = ssl.create_default_context()
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=tls_context, timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
            server.ehlo()
            server.starttls(context=tls_context)
            server.ehlo()

        with server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [TO_EMAIL], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        print("SMTP delivery failed: Gmail rejected the configured App Password.")
    except (OSError, smtplib.SMTPException) as exc:
        print(f"SMTP delivery failed: {exc}")


@app.post("/api/contact", status_code=202)
def send_contact_email(payload: ContactMessage, background_tasks: BackgroundTasks):
    if not SMTP_USER or not SMTP_PASS:
        raise HTTPException(
            status_code=500,
            detail="Email is not configured on the server. Set SMTP_USER / SMTP_PASS in .env",
        )

    background_tasks.add_task(deliver_contact_email, payload)
    return {"status": "queued"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
