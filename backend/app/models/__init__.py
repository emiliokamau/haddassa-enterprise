from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="client")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    email_confirmed_at = db.Column(db.DateTime, nullable=True)
    two_factor_enabled = db.Column(db.Boolean, nullable=False, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    email_notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client_profile = db.relationship(
        "ClientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def ensure_totp_secret(self):
        if not self.two_factor_secret:
            self.two_factor_secret = pyotp.random_base32()
        return self.two_factor_secret

    def get_totp_uri(self, issuer_name="Hadassah Enterprises"):
        secret = self.ensure_totp_secret()
        return pyotp.totp.TOTP(secret).provisioning_uri(name=self.email, issuer_name=issuer_name)

    def verify_totp(self, code):
        if not self.two_factor_secret:
            return False
        return pyotp.TOTP(self.two_factor_secret).verify((code or "").strip(), valid_window=1)

    @property
    def is_admin(self):
        return self.role == "admin"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON string
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))


class ClientProfile(db.Model):
    __tablename__ = "client_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="client_profile")
    filings = db.relationship("Filing", back_populates="client_profile", cascade="all, delete-orphan")


class Filing(db.Model):
    __tablename__ = "filings"

    id = db.Column(db.Integer, primary_key=True)
    client_profile_id = db.Column(db.Integer, db.ForeignKey("client_profiles.id"), nullable=False)
    filing_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="draft")
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client_profile = db.relationship("ClientProfile", back_populates="filings")
    documents = db.relationship("Document", back_populates="filing", cascade="all, delete-orphan")


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filing_id = db.Column(db.Integer, db.ForeignKey("filings.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    filing = db.relationship("Filing", back_populates="documents")


class ContactSubmission(db.Model):
    __tablename__ = "contact_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)
    message = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), nullable=False, default="website_contact_form")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ConsultationBooking(db.Model):
    __tablename__ = "consultation_bookings"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=False)
    service_interest = db.Column(db.String(120), nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    preferred_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="pending_confirmation")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)
    is_trusted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SiteUpdate(db.Model):
    __tablename__ = "site_updates"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    broadcast_requested = db.Column(db.Boolean, nullable=False, default=False)
    send_email = db.Column(db.Boolean, nullable=False, default=True)
    send_sms = db.Column(db.Boolean, nullable=False, default=False)
    send_whatsapp = db.Column(db.Boolean, nullable=False, default=False)
    schedule_type = db.Column(db.String(20), nullable=False, default="immediate")
    schedule_day = db.Column(db.Integer, nullable=True)
    schedule_month = db.Column(db.Integer, nullable=True)
    last_scheduled_run_on = db.Column(db.Date, nullable=True)
    broadcast_pending_count = db.Column(db.Integer, nullable=False, default=0)
    broadcast_success_count = db.Column(db.Integer, nullable=False, default=0)
    broadcast_failure_count = db.Column(db.Integer, nullable=False, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    created_by = db.relationship("User", backref=db.backref("site_updates", lazy="dynamic"))


class SiteUpdateDelivery(db.Model):
    __tablename__ = "site_update_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    site_update_id = db.Column(db.Integer, db.ForeignKey("site_updates.id"), nullable=False, index=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey("newsletter_subscribers.id"), nullable=True)
    recipient_name = db.Column(db.String(100), nullable=False)
    recipient_email = db.Column(db.String(255), nullable=True, index=True)
    recipient_phone = db.Column(db.String(32), nullable=True, index=True)
    channel = db.Column(db.String(20), nullable=False, default="email", index=True)
    dispatch_key = db.Column(db.String(20), nullable=False, default="manual", index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    site_update = db.relationship(
        "SiteUpdate",
        backref=db.backref("deliveries", lazy="dynamic", cascade="all, delete-orphan"),
    )
    subscriber = db.relationship("NewsletterSubscriber", backref=db.backref("site_update_deliveries", lazy="dynamic"))
