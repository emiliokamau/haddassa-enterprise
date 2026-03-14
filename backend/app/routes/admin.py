from datetime import datetime, time, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import (
    ClientProfile,
    ConsultationBooking,
    Filing,
    NewsletterSubscriber,
    SiteUpdate,
    User,
    db,
)
from ..services.audit import log_action
from ..services.authz import role_required
from ..services.broadcasts import enqueue_site_update_broadcast, requeue_failed_deliveries

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
        send_email = request.form.get("channel_email") == "yes"
        send_sms = request.form.get("channel_sms") == "yes"
        send_whatsapp = request.form.get("channel_whatsapp") == "yes"
        schedule_type = (request.form.get("schedule_type") or "immediate").strip().lower()
        schedule_day_value = (request.form.get("schedule_day") or "").strip()
        schedule_month_value = (request.form.get("schedule_month") or "").strip()

        if not title or not message:
            flash("Title and update message are required.", "error")
            return redirect(url_for("admin.updates"))

        if broadcast_requested and not any([send_email, send_sms, send_whatsapp]):
            flash("Select at least one delivery channel (email, SMS, or WhatsApp).", "error")
            return redirect(url_for("admin.updates"))

        if schedule_type not in {"immediate", "monthly", "yearly"}:
            flash("Invalid schedule type selected.", "error")
            return redirect(url_for("admin.updates"))

        schedule_day = None
        schedule_month = None
        if schedule_type in {"monthly", "yearly"}:
            try:
                schedule_day = int(schedule_day_value)
            except ValueError:
                schedule_day = None
            if schedule_day is None or schedule_day < 1 or schedule_day > 31:
                flash("Schedule day must be between 1 and 31.", "error")
                return redirect(url_for("admin.updates"))

        if schedule_type == "yearly":
            try:
                schedule_month = int(schedule_month_value)
            except ValueError:
                schedule_month = None
            if schedule_month is None or schedule_month < 1 or schedule_month > 12:
                flash("Schedule month must be between 1 and 12 for yearly reminders.", "error")
                return redirect(url_for("admin.updates"))

        update = SiteUpdate(
            title=title,
            message=message,
            broadcast_requested=broadcast_requested,
            send_email=send_email,
            send_sms=send_sms,
            send_whatsapp=send_whatsapp,
            schedule_type=schedule_type,
            schedule_day=schedule_day,
            schedule_month=schedule_month,
            created_by_user_id=current_user.id,
        )
        db.session.add(update)
        db.session.flush()

        pending_count = 0
        if broadcast_requested and schedule_type == "immediate":
            pending_count = enqueue_site_update_broadcast(update)

        log_action(
            "site_update_create",
            entity_type="site_update",
            details={
                "title": title,
                "broadcast_requested": broadcast_requested,
                "pending_count": pending_count,
            },
        )
        db.session.commit()

        if broadcast_requested:
            if schedule_type == "immediate":
                flash(
                    f"Update posted. Broadcast queued for {pending_count} delivery item(s).",
                    "success",
                )
            elif schedule_type == "monthly":
                flash("Update posted. Monthly reminder schedule saved.", "success")
            else:
                flash("Update posted. Yearly reminder schedule saved.", "success")
        else:
            flash("Update posted successfully.", "success")
        return redirect(url_for("admin.updates"))

    page_raw = request.args.get("page", "1").strip()
    try:
        page = max(int(page_raw), 1)
    except ValueError:
        page = 1

    per_page = 10
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    broadcast_filter = (request.args.get("broadcast_filter") or "all").strip().lower()

    query = SiteUpdate.query
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(SiteUpdate.created_at >= datetime.combine(from_date, time.min))
        except ValueError:
            flash("Invalid start date filter. Use YYYY-MM-DD.", "error")

    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(SiteUpdate.created_at <= datetime.combine(to_date, time.max))
        except ValueError:
            flash("Invalid end date filter. Use YYYY-MM-DD.", "error")

    if broadcast_filter == "broadcasted":
        query = query.filter(SiteUpdate.broadcast_requested.is_(True))
    elif broadcast_filter == "not_broadcasted":
        query = query.filter(SiteUpdate.broadcast_requested.is_(False))
    else:
        broadcast_filter = "all"

    total_updates = query.count()
    total_pages = max((total_updates + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages

    updates_list = (
        query.order_by(SiteUpdate.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    subscriber_count = NewsletterSubscriber.query.count()
    pending_queue_updates = SiteUpdate.query.filter(SiteUpdate.broadcast_pending_count > 0).count()
    return render_template(
        "admin_updates.html",
        updates=updates_list,
        subscriber_count=subscriber_count,
        page=page,
        total_pages=total_pages,
        total_updates=total_updates,
        date_from=date_from,
        date_to=date_to,
        broadcast_filter=broadcast_filter,
        pending_queue_updates=pending_queue_updates,
    )


@admin_bp.route("/updates/<int:update_id>/resend-failed", methods=["POST"])
@login_required
@role_required("admin")
def resend_failed_update_deliveries(update_id):
    update = db.session.get(SiteUpdate, update_id)
    if update is None:
        flash("Update not found.", "error")
        return redirect(url_for("admin.updates"))

    queued_count = requeue_failed_deliveries(update_id)
    if queued_count:
        log_action(
            "site_update_resend_failed",
            entity_type="site_update",
            entity_id=update_id,
            details={"queued_count": queued_count},
        )
        db.session.commit()
        flash(f"Queued {queued_count} failed delivery item(s) for resend.", "success")
    else:
        flash("No failed deliveries to resend for this update.", "info")

    return_to = (request.form.get("return_to") or "").strip()
    if return_to.startswith("/admin/updates"):
        return redirect(return_to)
    return redirect(url_for("admin.updates"))


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


