import random
import time
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from ..models import ClientProfile, User, db
from ..services.email import send_email
from ..services.sms import send_sms

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Sign In")


class TwoFactorVerifyForm(FlaskForm):
    otp_code = StringField("Authentication Code", validators=[DataRequired(), Length(min=6, max=8)])
    submit = SubmitField("Verify Code")


class TwoFactorSetupForm(FlaskForm):
    otp_code = StringField("Authentication Code", validators=[DataRequired(), Length(min=6, max=8)])
    submit = SubmitField("Enable 2FA")


class ResendConfirmationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField("Resend Confirmation")


class ForgotPasswordRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Set New Password")


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_token(email, purpose):
    return _serializer().dumps({"email": email, "purpose": purpose})


def _verify_token(token, purpose, max_age):
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if payload.get("purpose") != purpose:
        return None
    return (payload.get("email") or "").strip().lower()


def _send_confirmation_email(user):
    token = _generate_token(user.email, "confirm_email")
    confirm_link = url_for("auth.confirm_email", token=token, _external=True)
    return send_email(
        to_email=user.email,
        subject="Confirm your Hadassah Enterprises account",
        text_body=(
            "Welcome to Hadassah Enterprises. Confirm your email address by visiting this link:\n"
            f"{confirm_link}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


def _send_password_reset_email(user):
    token = _generate_token(user.email, "password_reset")
    reset_link = url_for("auth.reset_password", token=token, _external=True)
    return send_email(
        to_email=user.email,
        subject="Reset your Hadassah Enterprises password",
        text_body=(
            "A password reset was requested for your account. Use this link to set a new password:\n"
            f"{reset_link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
    )


def _get_user_sms_phone(user):
    if user.client_profile and user.client_profile.contact_phone:
        return user.client_profile.contact_phone.strip()
    return None


def _is_sms_otp_enabled():
    return bool(current_app.config.get("ENABLE_SMS_OTP", False))


def _send_sms_otp_for_pending_login(user):
    if not _is_sms_otp_enabled():
        return False

    to_number = _get_user_sms_phone(user)
    if not to_number:
        return False

    otp_code = f"{random.randint(0, 999999):06d}"
    session["pending_2fa_sms_hash"] = generate_password_hash(otp_code)
    session["pending_2fa_sms_expires"] = int(time.time()) + 300

    return send_sms(
        to_number=to_number,
        message=f"Your Hadassah Enterprises one-time verification code is {otp_code}. It expires in 5 minutes.",
    )


def _verify_pending_sms_otp(code):
    code_hash = session.get("pending_2fa_sms_hash")
    expires_at = int(session.get("pending_2fa_sms_expires") or 0)
    if not code_hash or expires_at < int(time.time()):
        return False
    return check_password_hash(code_hash, (code or "").strip())


def _clear_pending_2fa_session():
    session.pop("pending_2fa_user_id", None)
    session.pop("pending_2fa_sms_hash", None)
    session.pop("pending_2fa_sms_expires", None)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists.", "error")
            return render_template("register.html", form=form)

        role = "admin" if email == current_app.config["ADMIN_EMAIL"] else "client"
        user = User(
            email=email,
            role=role,
            email_confirmed=not current_app.config.get("EMAIL_CONFIRMATION_REQUIRED", True),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        if role == "client":
            profile = ClientProfile(
                user=user, company_name=form.full_name.data.strip()
            )
            db.session.add(profile)
        db.session.commit()

        if current_app.config.get("EMAIL_CONFIRMATION_REQUIRED", True):
            sent = _send_confirmation_email(user)
            if sent:
                flash("Account created. Please check your email to confirm your account before signing in.", "success")
            else:
                flash(
                    "Account created, but we could not send the confirmation email right now. "
                    "Please use Resend email confirmation.",
                    "error",
                )
        else:
            flash("Account created. You can now sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "error")
            return render_template("login.html", form=form)

        if not user.is_active:
            flash("Your account is inactive. Contact support.", "error")
            return render_template("login.html", form=form)

        if current_app.config.get("EMAIL_CONFIRMATION_REQUIRED", True) and not user.email_confirmed:
            flash("Please confirm your email before signing in.", "error")
            return redirect(url_for("auth.resend_confirmation"))

        if user.two_factor_enabled and user.two_factor_secret:
            session["pending_2fa_user_id"] = user.id
            sms_sent = _send_sms_otp_for_pending_login(user)
            if sms_sent:
                flash("Enter your authenticator code or SMS code to complete sign in.", "success")
            else:
                flash("Enter your 2FA code to complete sign in.", "success")
            return redirect(url_for("auth.login_two_factor"))

        login_user(user)
        flash("Welcome back.", "success")

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("client.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/2fa", methods=["GET", "POST"])
def login_two_factor():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    user_id = session.get("pending_2fa_user_id")
    if not user_id:
        flash("Your 2FA session has expired. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, int(user_id))
    if not user or not user.two_factor_enabled:
        _clear_pending_2fa_session()
        flash("Unable to complete 2FA verification. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    form = TwoFactorVerifyForm()
    if form.validate_on_submit():
        otp = form.otp_code.data
        valid_totp = user.verify_totp(otp)
        valid_sms = _verify_pending_sms_otp(otp)
        if not valid_totp and not valid_sms:
            flash("Invalid authentication code.", "error")
            return render_template("auth_2fa_verify.html", form=form)

        _clear_pending_2fa_session()
        login_user(user)
        flash("Welcome back.", "success")

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("client.dashboard"))

    return render_template("auth_2fa_verify.html", form=form)


@auth_bp.route("/2fa/resend-sms", methods=["POST"])
def resend_login_two_factor_sms():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    user_id = session.get("pending_2fa_user_id")
    if not user_id:
        flash("Your 2FA session has expired. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, int(user_id))
    if not user:
        _clear_pending_2fa_session()
        flash("Unable to resend SMS code. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    if _send_sms_otp_for_pending_login(user):
        flash("A new SMS verification code has been sent.", "success")
    else:
        flash("SMS verification is unavailable for this account.", "error")
    return redirect(url_for("auth.login_two_factor"))


@auth_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_two_factor():
    form = TwoFactorSetupForm()

    # Keep existing secret stable so authenticator apps do not break after refresh.
    current_user.ensure_totp_secret()
    qr_uri = current_user.get_totp_uri()

    if form.validate_on_submit():
        if not current_user.verify_totp(form.otp_code.data):
            flash("Invalid code. Use the current code from your authenticator app.", "error")
            return render_template(
                "auth_2fa_setup.html",
                form=form,
                totp_secret=current_user.two_factor_secret,
                qr_uri=qr_uri,
            )

        current_user.two_factor_enabled = True
        db.session.commit()
        flash("Two-factor authentication enabled.", "success")
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("client.dashboard"))

    return render_template(
        "auth_2fa_setup.html",
        form=form,
        totp_secret=current_user.two_factor_secret,
        qr_uri=qr_uri,
    )


@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def disable_two_factor():
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    db.session.commit()
    flash("Two-factor authentication disabled.", "success")
    if current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("client.dashboard"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    _clear_pending_2fa_session()
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("public.home"))


@auth_bp.route("/confirm-email/<token>", methods=["GET"])
def confirm_email(token):
    email = _verify_token(
        token,
        purpose="confirm_email",
        max_age=int(current_app.config.get("EMAIL_TOKEN_MAX_AGE_SECONDS", 86400)),
    )
    if not email:
        flash("This confirmation link is invalid or expired.", "error")
        return redirect(url_for("auth.resend_confirmation"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Unable to confirm that account.", "error")
        return redirect(url_for("auth.login"))

    if not user.email_confirmed:
        user.email_confirmed = True
        user.email_confirmed_at = datetime.utcnow()
        db.session.commit()

    flash("Email confirmed. You can now sign in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-confirmation", methods=["GET", "POST"])
def resend_confirmation():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    form = ResendConfirmationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and not user.email_confirmed:
            sent = _send_confirmation_email(user)
            if not sent:
                current_app.logger.warning("Confirmation email resend failed for user_id=%s", user.id)

        flash("If an account exists and is unconfirmed, a new confirmation email has been sent.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth_resend_confirmation.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    form = ForgotPasswordRequestForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.is_active:
            sent = _send_password_reset_email(user)
            if not sent:
                current_app.logger.warning("Password reset email send failed for user_id=%s", user.id)

        flash("If an account exists for this email, a password reset link has been sent.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth_forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    email = _verify_token(
        token,
        purpose="password_reset",
        max_age=int(current_app.config.get("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", 3600)),
    )
    if not email:
        flash("This password reset link is invalid or expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        flash("Unable to reset password for this account.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated. You can now sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth_reset_password.html", form=form)
