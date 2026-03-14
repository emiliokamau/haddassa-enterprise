import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _normalize_database_url(database_url: str) -> str:
    # Render Postgres URLs may be provided as postgres:// or postgresql://.
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://root:42125811Kamau@localhost:3760/hadassah_enterprises",
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "emiliokamau35@gmail.com")
    WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "254796526647")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kamau.emilio@s.karu.ac.ke").lower()

    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024

    # Session and CSRF security defaults. Promote secure values in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    WTF_CSRF_TIME_LIMIT = 3600

    # HTTP security headers
    ENABLE_SECURITY_HEADERS = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true"
    CONTENT_SECURITY_POLICY = os.getenv(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    X_CONTENT_TYPE_OPTIONS = "nosniff"
    X_FRAME_OPTIONS = "DENY"
    REFERRER_POLICY = "strict-origin-when-cross-origin"

    # Email API integration (Resend)
    ENABLE_EMAIL_NOTIFICATIONS = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "true").lower() == "true"
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend").lower()
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "emiliokamau35@gmail.com")

    # Account security flows
    EMAIL_CONFIRMATION_REQUIRED = os.getenv("EMAIL_CONFIRMATION_REQUIRED", "true").lower() == "true"
    EMAIL_TOKEN_MAX_AGE_SECONDS = int(os.getenv("EMAIL_TOKEN_MAX_AGE_SECONDS", "86400"))
    PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = int(os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", "3600"))
    BOOKING_CONFIRMATION_TOKEN_MAX_AGE_SECONDS = int(os.getenv("BOOKING_CONFIRMATION_TOKEN_MAX_AGE_SECONDS", "3600"))

    # Optional Twilio SMS one-time code flow
    ENABLE_SMS_OTP = os.getenv("ENABLE_SMS_OTP", "false").lower() == "true"
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

    # Optional Twilio WhatsApp template messaging (Content API)
    ENABLE_TWILIO_WHATSAPP = os.getenv("ENABLE_TWILIO_WHATSAPP", "false").lower() == "true"
    TWILIO_WHATSAPP_FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_FROM_NUMBER", "whatsapp:+14155238886")
    TWILIO_WHATSAPP_BOOKING_CONTENT_SID = os.getenv("TWILIO_WHATSAPP_BOOKING_CONTENT_SID", "")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    environment = os.getenv("FLASK_ENV", "development").lower()
    return config_by_name.get(environment, DevelopmentConfig)

