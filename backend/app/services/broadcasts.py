from datetime import date, datetime

from flask import current_app

from ..models import NewsletterSubscriber, SiteUpdate, SiteUpdateDelivery, db
from .email import send_email
from .sms import send_sms
from .whatsapp import send_whatsapp_text


def enqueue_due_scheduled_updates(run_on: date | None = None) -> dict:
    run_on = run_on or date.today()
    updates = SiteUpdate.query.filter(
        SiteUpdate.broadcast_requested.is_(True),
        SiteUpdate.schedule_type.in_(["monthly", "yearly"]),
    ).all()

    queued_updates = 0
    queued_deliveries = 0
    for update in updates:
        if not _is_due(update, run_on):
            continue

        dispatch_key = _dispatch_key(update.schedule_type, run_on)
        queued = enqueue_site_update_broadcast(update, dispatch_key=dispatch_key)
        update.last_scheduled_run_on = run_on
        queued_updates += 1
        queued_deliveries += queued

    if queued_updates:
        db.session.commit()

    return {
        "updates_queued": queued_updates,
        "deliveries_queued": queued_deliveries,
    }


def enqueue_site_update_broadcast(site_update: SiteUpdate, dispatch_key: str = "manual") -> int:
    subscribers = NewsletterSubscriber.query.order_by(NewsletterSubscriber.id.asc()).all()
    channels = _selected_channels(site_update)
    queued = 0

    for subscriber in subscribers:
        for channel in channels:
            delivery = SiteUpdateDelivery(
                site_update_id=site_update.id,
                subscriber_id=subscriber.id,
                recipient_name=subscriber.full_name,
                recipient_email=subscriber.email,
                recipient_phone=(subscriber.phone or "").strip() or None,
                channel=channel,
                dispatch_key=dispatch_key,
                status="pending",
            )
            db.session.add(delivery)
            queued += 1

    site_update.broadcast_pending_count = (site_update.broadcast_pending_count or 0) + queued
    return queued


def process_site_update_queue(batch_size: int = 100, retry_failed: bool = False) -> dict:
    statuses = ["pending", "processing"]
    if retry_failed:
        statuses.append("failed")

    query = SiteUpdateDelivery.query.filter(SiteUpdateDelivery.status.in_(statuses)).order_by(
        SiteUpdateDelivery.created_at.asc(), SiteUpdateDelivery.id.asc()
    )
    deliveries = query.limit(batch_size).all()

    processed = 0
    sent = 0
    failed = 0

    for delivery in deliveries:
        delivery.status = "processing"
        db.session.flush()

        site_update = db.session.get(SiteUpdate, delivery.site_update_id)
        if site_update is None:
            delivery.status = "failed"
            delivery.last_error = "Site update no longer exists"
            delivery.attempt_count += 1
            failed += 1
            processed += 1
            continue

        ok, error_text = _send_delivery(site_update, delivery)

        delivery.attempt_count += 1
        processed += 1

        if ok:
            delivery.status = "sent"
            delivery.sent_at = datetime.utcnow()
            delivery.last_error = None
            sent += 1
        else:
            delivery.status = "failed"
            delivery.last_error = error_text
            failed += 1

    _refresh_site_update_counts()
    db.session.commit()

    current_app.logger.info(
        "Processed site update queue: processed=%s sent=%s failed=%s retry_failed=%s",
        processed,
        sent,
        failed,
        retry_failed,
    )

    return {
        "processed": processed,
        "sent": sent,
        "failed": failed,
    }


def requeue_failed_deliveries(site_update_id: int) -> int:
    deliveries = SiteUpdateDelivery.query.filter_by(site_update_id=site_update_id, status="failed").all()
    queued_count = 0
    for delivery in deliveries:
        delivery.status = "pending"
        delivery.last_error = None
        queued_count += 1

    _refresh_site_update_counts()
    return queued_count


def _selected_channels(site_update: SiteUpdate) -> list[str]:
    channels = []
    if site_update.send_email:
        channels.append("email")
    if site_update.send_sms:
        channels.append("sms")
    if site_update.send_whatsapp:
        channels.append("whatsapp")
    if not channels:
        channels.append("email")
    return channels


def _send_delivery(site_update: SiteUpdate, delivery: SiteUpdateDelivery) -> tuple[bool, str]:
    message = (
        f"Hello {delivery.recipient_name},\n\n"
        f"{site_update.message}\n\n"
        "Thank you for trusting Hadassah Enterprises."
    )

    if delivery.channel == "email":
        if not delivery.recipient_email:
            return False, "Missing recipient email"
        ok = send_email(
            to_email=delivery.recipient_email,
            subject=f"Hadassah Site Update: {site_update.title}",
            text_body=message,
        )
        return ok, "Email provider returned failure"

    if delivery.channel == "sms":
        if not delivery.recipient_phone:
            return False, "Missing recipient phone for SMS"
        ok = send_sms(to_number=delivery.recipient_phone, message=message)
        return ok, "SMS provider returned failure"

    if delivery.channel == "whatsapp":
        if not delivery.recipient_phone:
            return False, "Missing recipient phone for WhatsApp"
        ok = send_whatsapp_text(to_number=delivery.recipient_phone, body=message)
        return ok, "WhatsApp provider returned failure"

    return False, f"Unsupported channel: {delivery.channel}"


def _is_due(update: SiteUpdate, run_on: date) -> bool:
    if update.schedule_type == "monthly":
        if update.schedule_day is None or update.schedule_day != run_on.day:
            return False
        if update.last_scheduled_run_on is None:
            return True
        return (
            update.last_scheduled_run_on.year != run_on.year
            or update.last_scheduled_run_on.month != run_on.month
        )

    if update.schedule_type == "yearly":
        if update.schedule_month is None or update.schedule_day is None:
            return False
        if update.schedule_month != run_on.month or update.schedule_day != run_on.day:
            return False
        return update.last_scheduled_run_on != run_on

    return False


def _dispatch_key(schedule_type: str, run_on: date) -> str:
    if schedule_type == "monthly":
        return run_on.strftime("%Y-%m")
    if schedule_type == "yearly":
        return run_on.strftime("%Y")
    return "manual"


def _refresh_site_update_counts() -> None:
    update_ids = [row.id for row in SiteUpdate.query.with_entities(SiteUpdate.id).all()]
    for update_id in update_ids:
        sent_count = SiteUpdateDelivery.query.filter_by(site_update_id=update_id, status="sent").count()
        failed_count = SiteUpdateDelivery.query.filter_by(site_update_id=update_id, status="failed").count()
        pending_count = SiteUpdateDelivery.query.filter(
            SiteUpdateDelivery.site_update_id == update_id,
            SiteUpdateDelivery.status.in_(["pending", "processing"]),
        ).count()

        site_update = db.session.get(SiteUpdate, update_id)
        if site_update:
            site_update.broadcast_success_count = sent_count
            site_update.broadcast_failure_count = failed_count
            site_update.broadcast_pending_count = pending_count
