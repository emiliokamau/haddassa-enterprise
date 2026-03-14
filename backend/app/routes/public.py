from datetime import date
from urllib.parse import quote_plus

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField, TimeField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, ValidationError

from ..models import ConsultationBooking, ContactSubmission, NewsletterSubscriber, db
from ..services.email import send_email
from ..services.whatsapp import send_whatsapp_template, send_whatsapp_text

public_bp = Blueprint("public", __name__)


def _booking_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_booking_confirmation_token(booking_id: int) -> str:
    return _booking_serializer().dumps({"booking_id": booking_id, "purpose": "booking_confirmation"})


def _verify_booking_confirmation_token(token: str, max_age: int) -> int | None:
    try:
        payload = _booking_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    if payload.get("purpose") != "booking_confirmation":
        return None

    booking_id = payload.get("booking_id")
    if not isinstance(booking_id, int) or booking_id <= 0:
        return None
    return booking_id


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Length(max=32),
            Regexp(r"^[0-9+\-\s()]{7,32}$", message="Enter a valid phone number."),
        ],
    )
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Send Message")


class ConsultationBookingForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField(
        "Phone",
        validators=[
            DataRequired(),
            Length(max=32),
            Regexp(r"^[0-9+\-\s()]{7,32}$", message="Enter a valid phone number."),
        ],
    )
    service_interest = SelectField(
        "Service of Interest",
        validators=[DataRequired()],
        choices=[
            ("Audit", "Audit"),
            ("Bookkeeping", "Bookkeeping"),
            ("Tax Services", "Tax Services"),
            ("Company & Business Name Registration", "Company & Business Name Registration"),
        ],
    )
    preferred_date = DateField("Preferred Date", validators=[DataRequired()])
    preferred_time = TimeField("Preferred Time", validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Book Consultation")

    def validate_preferred_date(self, field):
        if field.data < date.today():
            raise ValidationError("Please choose a present or future date.")


def _normalized_whatsapp_number(raw_number: str) -> str:
    return "".join(ch for ch in raw_number if ch.isdigit())


def _notify_support(subject: str, message: str):
    support_email = (current_app.config.get("SUPPORT_EMAIL") or "").strip()
    if not support_email:
        return False
    return send_email(to_email=support_email, subject=subject, text_body=message)


def _send_booking_whatsapp_confirmation(booking: ConsultationBooking):
    content_sid = (current_app.config.get("TWILIO_WHATSAPP_BOOKING_CONTENT_SID") or "").strip()
    preferred_date = booking.preferred_date.strftime("%m/%d")
    preferred_time = booking.preferred_time.strftime("%I:%M %p").lstrip("0")

    if content_sid:
        content_variables = {"1": preferred_date, "2": preferred_time}
        return send_whatsapp_template(
            to_number=booking.phone,
            content_sid=content_sid,
            content_variables=content_variables,
        )

    # Fallback to plain WhatsApp text if template Content SID is not configured yet.
    return send_whatsapp_text(
        to_number=booking.phone,
        body=(
            "Hadassah Enterprises booking received. "
            f"Preferred slot: {preferred_date} at {preferred_time}. "
            "We will confirm shortly."
        ),
    )


@public_bp.route("/")
def home():
    return render_template("home.html")


@public_bp.route("/about")
def about():
    return render_template("about.html")


@public_bp.route("/services")
def services():
    return render_template("services.html")


@public_bp.route("/compliance-calendar")
def compliance_calendar():
    return render_template("compliance_calendar.html")


@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        submission = ContactSubmission(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip() or None,
            message=form.message.data.strip(),
        )
        db.session.add(submission)
        db.session.commit()

        _notify_support(
            subject="New Website Contact Submission",
            message=(
                f"Name: {submission.name}\n"
                f"Email: {submission.email}\n"
                f"Phone: {submission.phone or 'N/A'}\n"
                f"Message:\n{submission.message}"
            ),
        )

        support_email = current_app.config.get("SUPPORT_EMAIL")
        whatsapp_number = _normalized_whatsapp_number(current_app.config.get("WHATSAPP_NUMBER", ""))
        whatsapp_message = (
            f"Hello Hadassah Enterprises, I am {submission.name}. "
            f"I would like assistance with: {submission.message}"
        )
        whatsapp_url = None
        if whatsapp_number:
            whatsapp_url = f"https://wa.me/{whatsapp_number}?text={quote_plus(whatsapp_message)}"

        mailto_url = (
            f"mailto:{support_email}?subject={quote_plus('Website Contact - Hadassah Enterprises')}"
            f"&body={quote_plus(whatsapp_message)}"
        )

        flash("Your message has been received. We will reach out shortly.", "success")
        return render_template(
            "contact_success.html",
            submission=submission,
            whatsapp_url=whatsapp_url,
            mailto_url=mailto_url,
            support_email=support_email,
        )

    return render_template("contact.html", form=form)


@public_bp.route("/book-consultation", methods=["GET", "POST"])
def book_consultation():
    if current_user.is_authenticated and current_user.role == "admin":
        flash("Admin accounts cannot book consultation sessions.", "error")
        return redirect(url_for("admin.dashboard"))

    form = ConsultationBookingForm()
    if form.validate_on_submit():
        booking = ConsultationBooking(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip(),
            service_interest=form.service_interest.data,
            preferred_date=form.preferred_date.data,
            preferred_time=form.preferred_time.data,
            notes=(form.notes.data or "").strip() or None,
        )
        db.session.add(booking)
        db.session.commit()

        _notify_support(
            subject="New Consultation Booking",
            message=(
                f"Name: {booking.full_name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone}\n"
                f"Service: {booking.service_interest}\n"
                f"Preferred Date: {booking.preferred_date}\n"
                f"Preferred Time: {booking.preferred_time}\n"
                f"Notes: {booking.notes or 'N/A'}"
            ),
        )
        _send_booking_whatsapp_confirmation(booking)
        confirmation_token = _generate_booking_confirmation_token(booking.id)
        return redirect(url_for("public.booking_confirmation", token=confirmation_token))

    return render_template("book_consultation.html", form=form)


@public_bp.route("/book-consultation/confirmation/<token>")
def booking_confirmation(token):
    max_age = int(current_app.config.get("BOOKING_CONFIRMATION_TOKEN_MAX_AGE_SECONDS", 3600))
    booking_id = _verify_booking_confirmation_token(token, max_age=max_age)
    if booking_id is None:
        flash("This booking confirmation link is invalid or expired.", "error")
        return redirect(url_for("public.book_consultation"))

    booking = db.session.get(ConsultationBooking, booking_id)
    if booking is None:
        flash("Unable to locate this booking confirmation.", "error")
        return redirect(url_for("public.book_consultation"))

    return render_template("booking_confirmation.html", booking=booking)


@public_bp.route("/subscribe", methods=["POST"])
def subscribe_newsletter():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip() or None
    trusted_confirm = request.form.get("trusted_confirm") == "yes"

    if not full_name or not email:
        flash("Please provide your full name and email to subscribe.", "error")
        return redirect(request.referrer or url_for("public.home"))

    if not trusted_confirm:
        flash("Subscription is for trusted clients only. Please confirm to continue.", "error")
        return redirect(request.referrer or url_for("public.home"))

    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        flash("This email is already subscribed to monthly compliance updates.", "success")
        return redirect(request.referrer or url_for("public.home"))

    subscriber = NewsletterSubscriber(
        full_name=full_name,
        email=email,
        phone=phone,
        is_trusted=True,
    )
    db.session.add(subscriber)
    db.session.commit()

    send_email(
        to_email=subscriber.email,
        subject="You are subscribed to Hadassah monthly updates",
        text_body=(
            "Thank you for subscribing. You will receive monthly reminders on tax returns, "
            "filing deadlines, and compliance updates."
        ),
    )
    _notify_support(
        subject="New Trusted Newsletter Subscriber",
        message=f"{subscriber.full_name} <{subscriber.email}> subscribed to monthly updates.",
    )

    flash("Subscribed successfully. You will receive monthly filing and returns updates.", "success")
    return redirect(request.referrer or url_for("public.home"))










