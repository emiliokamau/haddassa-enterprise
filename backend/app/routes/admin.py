from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import ClientProfile, ConsultationBooking, Filing, NewsletterSubscriber, SiteUpdate, User, db
from ..services.audit import log_action
from ..services.authz import role_required
from ..services.email import send_email

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

FILING_STATUSES = ["draft", "submitted", "under_review", "completed", "cancelled"]
BOOKING_STATUSES = ["pending_confirmation", "confirmed", "completed", "cancelled"]


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    total_clients = ClientProfile.query.count()

    now = datetime.utcnow()
    week_ahead = now + timedelta(days=7)

    pending_filings = Filing.query.filter(
        Filing.status.in_(["draft", "submitted", "under_review"])
    ).count()
    upcoming_filings = Filing.query.filter(
        Filing.due_date.between(now, week_ahead),
        Filing.status.notin_(["completed", "cancelled"]),
    ).count()
    overdue_filings = Filing.query.filter(
        Filing.due_date < now,
        Filing.status.notin_(["completed", "cancelled"]),
    ).count()
    pending_bookings = ConsultationBooking.query.filter_by(
        status="pending_confirmation"
    ).count()

    return render_template(
        "admin_dashboard.html",
        total_clients=total_clients,
        pending_filings=pending_filings,
        upcoming_filings=upcoming_filings,
        overdue_filings=overdue_filings,
        pending_bookings=pending_bookings,
    )


@admin_bp.route("/clients")
@login_required
@role_required("admin")
def clients():
    q = request.args.get("q", "").strip()
    query = ClientProfile.query.join(User)
    if q:
        query = query.filter(
            db.or_(
                ClientProfile.company_name.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )
    profiles = query.order_by(ClientProfile.company_name.asc()).all()
    return render_template("admin_clients.html", profiles=profiles, q=q)


@admin_bp.route("/filings")
@login_required
@role_required("admin")
def filings():
    status_filter = request.args.get("status", "").strip()
    query = Filing.query.join(ClientProfile)
    if status_filter and status_filter in FILING_STATUSES:
        query = query.filter(Filing.status == status_filter)
    all_filings = query.order_by(Filing.due_date.asc()).all()
    return render_template(
        "admin_filings.html",
        filings=all_filings,
        statuses=FILING_STATUSES,
        current_status=status_filter,
    )


@admin_bp.route("/filings/<int:filing_id>/status", methods=["POST"])
@login_required
@role_required("admin")
def update_filing_status(filing_id):
    filing = db.session.get(Filing, filing_id)
    if filing is None:
        flash("Filing not found.", "error")
        return redirect(url_for("admin.filings"))
    new_status = request.form.get("status", "").strip()
    if new_status not in FILING_STATUSES:
        flash("Invalid status value.", "error")
        return redirect(url_for("admin.filings"))
    old_status = filing.status
    filing.status = new_status
    log_action(
        "filing_status_update",
        entity_type="filing",
        entity_id=filing_id,
        details={"from": old_status, "to": new_status},
    )
    db.session.commit()
    flash(f"Filing updated to '{new_status.replace('_', ' ')}'.", "success")
    return redirect(url_for("admin.filings"))


@admin_bp.route("/bookings")
@login_required
@role_required("admin")
def bookings():
    status_filter = request.args.get("status", "").strip()
    query = ConsultationBooking.query
    if status_filter and status_filter in BOOKING_STATUSES:
        query = query.filter(ConsultationBooking.status == status_filter)
    all_bookings = query.order_by(
        ConsultationBooking.preferred_date.asc(),
        ConsultationBooking.preferred_time.asc(),
    ).all()
    return render_template(
        "admin_bookings.html",
        bookings=all_bookings,
        statuses=BOOKING_STATUSES,
        current_status=status_filter,
    )


@admin_bp.route("/updates", methods=["GET", "POST"])
@login_required
@role_required("admin")
def updates():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        message = (request.form.get("message") or "").strip()
        broadcast_requested = request.form.get("broadcast_subscribers") == "yes"

        if not title or not message:
            flash("Title and update message are required.", "error")
            return redirect(url_for("admin.updates"))

        update = SiteUpdate(
            title=title,
            message=message,
            broadcast_requested=broadcast_requested,
            created_by_user_id=current_user.id,
        )
        db.session.add(update)

        success_count = 0
        failure_count = 0
        if broadcast_requested:
            subscribers = NewsletterSubscriber.query.order_by(NewsletterSubscriber.id.asc()).all()
            for subscriber in subscribers:
                sent = send_email(
                    to_email=subscriber.email,
                    subject=f"Hadassah Site Update: {title}",
                    text_body=(
                        f"Hello {subscriber.full_name},\n\n"
                        f"{message}\n\n"
                        "Thank you for trusting Hadassah Enterprises."
                    ),
                )
                if sent:
                    success_count += 1
                else:
                    failure_count += 1

        update.broadcast_success_count = success_count
        update.broadcast_failure_count = failure_count

        log_action(
            "site_update_create",
            entity_type="site_update",
            details={
                "title": title,
                "broadcast_requested": broadcast_requested,
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )
        db.session.commit()

        if broadcast_requested:
            flash(
                f"Update posted. Broadcast sent to {success_count} subscriber(s), {failure_count} failed.",
                "success",
            )
        else:
            flash("Update posted successfully.", "success")
        return redirect(url_for("admin.updates"))

    updates_list = SiteUpdate.query.order_by(SiteUpdate.created_at.desc()).all()
    subscriber_count = NewsletterSubscriber.query.count()
    return render_template(
        "admin_updates.html",
        updates=updates_list,
        subscriber_count=subscriber_count,
    )


@admin_bp.route("/bookings/<int:booking_id>/status", methods=["POST"])
@login_required
@role_required("admin")
def update_booking_status(booking_id):
    booking = db.session.get(ConsultationBooking, booking_id)
    if booking is None:
        flash("Booking not found.", "error")
        return redirect(url_for("admin.bookings"))
    new_status = request.form.get("status", "").strip()
    if new_status not in BOOKING_STATUSES:
        flash("Invalid status value.", "error")
        return redirect(url_for("admin.bookings"))
    booking.status = new_status
    log_action(
        "booking_status_update",
        entity_type="booking",
        entity_id=booking_id,
        details={"status": new_status},
    )
    db.session.commit()
    flash(f"Booking updated to '{new_status.replace('_', ' ')}'.", "success")
    return redirect(url_for("admin.bookings"))

