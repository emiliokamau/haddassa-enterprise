from datetime import date, datetime

from app.models import (
    ConsultationBooking,
    NewsletterSubscriber,
    SiteUpdate,
    SiteUpdateDelivery,
    User,
    db,
)
from app.services.broadcasts import enqueue_due_scheduled_updates, process_site_update_queue


def create_user(email, password, role="client"):
    user = User(email=email, role=role, email_confirmed=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_admin_updates_requires_admin_role(app, client):
    with app.app_context():
        create_user("client-updates@example.com", "pass12345", role="client")

    login(client, "client-updates@example.com", "pass12345")
    response = client.get("/admin/updates")
    assert response.status_code == 403


def test_admin_can_view_and_post_updates(app, client):
    with app.app_context():
        create_user("admin-updates@example.com", "pass12345", role="admin")

    login(client, "admin-updates@example.com", "pass12345")

    get_response = client.get("/admin/updates")
    assert get_response.status_code == 200

    post_response = client.post(
        "/admin/updates",
        data={
            "title": "Tax Reminder",
            "message": "Please submit VAT returns by the 20th.",
        },
        follow_redirects=False,
    )
    assert post_response.status_code in (301, 302)
    assert "/admin/updates" in post_response.location

    with app.app_context():
        update = SiteUpdate.query.filter_by(title="Tax Reminder").first()
        assert update is not None
        assert update.broadcast_requested is False


def test_admin_update_broadcast_enqueues_deliveries(app, client):
    with app.app_context():
        create_user("admin-queue@example.com", "pass12345", role="admin")
        db.session.add(
            NewsletterSubscriber(full_name="Alice", email="alice@example.com", is_trusted=True)
        )
        db.session.add(
            NewsletterSubscriber(full_name="Bob", email="bob@example.com", is_trusted=True)
        )
        db.session.commit()

    login(client, "admin-queue@example.com", "pass12345")

    response = client.post(
        "/admin/updates",
        data={
            "title": "Compliance Update",
            "message": "Quarterly filing window is open.",
            "broadcast_subscribers": "yes",
            "channel_email": "yes",
            "schedule_type": "immediate",
        },
        follow_redirects=False,
    )
    assert response.status_code in (301, 302)

    with app.app_context():
        update = SiteUpdate.query.filter_by(title="Compliance Update").first()
        assert update is not None
        assert update.broadcast_requested is True
        assert update.broadcast_pending_count == 2
        assert update.broadcast_success_count == 0
        assert update.broadcast_failure_count == 0

        deliveries = SiteUpdateDelivery.query.filter_by(site_update_id=update.id).all()
        assert len(deliveries) == 2
        assert all(d.status == "pending" for d in deliveries)


def test_broadcast_processing_updates_counts(app, monkeypatch):
    with app.app_context():
        admin = create_user("admin-process@example.com", "pass12345", role="admin")
        update = SiteUpdate(
            title="Deadline Notice",
            message="Paye returns are due this week.",
            broadcast_requested=True,
            created_by_user_id=admin.id,
            broadcast_pending_count=2,
        )
        db.session.add(update)
        db.session.flush()

        db.session.add(
            SiteUpdateDelivery(
                site_update_id=update.id,
                recipient_name="Alice",
                recipient_email="alice@example.com",
                channel="email",
                status="pending",
            )
        )
        db.session.add(
            SiteUpdateDelivery(
                site_update_id=update.id,
                recipient_name="Bob",
                recipient_email="bob@example.com",
                channel="email",
                status="pending",
            )
        )
        db.session.commit()

        def fake_send_email(to_email, subject, text_body, html_body=None):
            return to_email != "bob@example.com"

        monkeypatch.setattr("app.services.broadcasts.send_email", fake_send_email)
        result = process_site_update_queue(batch_size=10)

        assert result["processed"] == 2
        assert result["sent"] == 1
        assert result["failed"] == 1

        refreshed = db.session.get(SiteUpdate, update.id)
        assert refreshed.broadcast_pending_count == 0
        assert refreshed.broadcast_success_count == 1
        assert refreshed.broadcast_failure_count == 1


def test_scheduled_monthly_and_yearly_updates_enqueue_when_due(app):
    with app.app_context():
        admin = create_user("admin-schedule@example.com", "pass12345", role="admin")
        db.session.add(
            NewsletterSubscriber(
                full_name="Scheduled User",
                email="scheduled@example.com",
                phone="+254700123456",
                is_trusted=True,
            )
        )
        db.session.flush()

        monthly = SiteUpdate(
            title="Monthly Reminder",
            message="Monthly deadline notice.",
            broadcast_requested=True,
            send_email=True,
            schedule_type="monthly",
            schedule_day=14,
            created_by_user_id=admin.id,
        )
        yearly = SiteUpdate(
            title="Yearly Reminder",
            message="Annual filing reminder.",
            broadcast_requested=True,
            send_email=True,
            schedule_type="yearly",
            schedule_day=14,
            schedule_month=3,
            created_by_user_id=admin.id,
        )
        db.session.add(monthly)
        db.session.add(yearly)
        db.session.commit()

        result = enqueue_due_scheduled_updates(run_on=date(2026, 3, 14))
        assert result["updates_queued"] == 2
        assert result["deliveries_queued"] == 2

        monthly_delivery_count = SiteUpdateDelivery.query.filter_by(site_update_id=monthly.id).count()
        yearly_delivery_count = SiteUpdateDelivery.query.filter_by(site_update_id=yearly.id).count()
        assert monthly_delivery_count == 1
        assert yearly_delivery_count == 1


def test_admin_cannot_post_consultation_booking(app, client):
    with app.app_context():
        create_user("admin-booking@example.com", "pass12345", role="admin")

    login(client, "admin-booking@example.com", "pass12345")

    response = client.post(
        "/book-consultation",
        data={
            "full_name": "Admin User",
            "email": "admin-booking@example.com",
            "phone": "+254700000001",
            "service_interest": "Audit",
            "preferred_date": date.today().isoformat(),
            "preferred_time": "10:30",
            "notes": "Should be blocked",
        },
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/admin/dashboard" in response.location

    with app.app_context():
        count = ConsultationBooking.query.filter_by(email="admin-booking@example.com").count()
        assert count == 0


def test_updates_filter_and_pagination(app, client):
    with app.app_context():
        create_user("admin-filter@example.com", "pass12345", role="admin")

        for i in range(12):
            db.session.add(
                SiteUpdate(
                    title=f"Update {i}",
                    message="Content",
                    broadcast_requested=(i % 2 == 0),
                    send_email=True,
                )
            )
        db.session.commit()

    login(client, "admin-filter@example.com", "pass12345")

    first_page = client.get("/admin/updates")
    assert first_page.status_code == 200
    assert b"Page 1 of 2" in first_page.data

    second_page = client.get("/admin/updates?page=2")
    assert second_page.status_code == 200
    assert b"Page 2 of 2" in second_page.data

    broadcasted_only = client.get("/admin/updates?broadcast_filter=broadcasted")
    assert broadcasted_only.status_code == 200
    assert b"Not sent" not in broadcasted_only.data


def test_resend_failed_deliveries_action(app, client):
    with app.app_context():
        admin = create_user("admin-resend@example.com", "pass12345", role="admin")
        update = SiteUpdate(
            title="Resend Me",
            message="Retry failed deliveries.",
            broadcast_requested=True,
            created_by_user_id=admin.id,
            broadcast_pending_count=0,
            broadcast_success_count=0,
            broadcast_failure_count=1,
            send_email=True,
        )
        db.session.add(update)
        db.session.flush()

        db.session.add(
            SiteUpdateDelivery(
                site_update_id=update.id,
                recipient_name="Retry User",
                recipient_email="retry@example.com",
                channel="email",
                status="failed",
                last_error="provider timeout",
            )
        )
        db.session.commit()

        update_id = update.id

    login(client, "admin-resend@example.com", "pass12345")
    response = client.post(
        f"/admin/updates/{update_id}/resend-failed",
        data={"return_to": "/admin/updates?broadcast_filter=broadcasted"},
        follow_redirects=False,
    )
    assert response.status_code in (301, 302)
    assert "/admin/updates?broadcast_filter=broadcasted" in response.location

    with app.app_context():
        delivery = SiteUpdateDelivery.query.filter_by(site_update_id=update_id).first()
        assert delivery is not None
        assert delivery.status == "pending"
        refreshed_update = db.session.get(SiteUpdate, update_id)
        assert refreshed_update.broadcast_pending_count == 1
        assert refreshed_update.broadcast_failure_count == 0

def test_broadcast_enqueues_trusted_subscribers_only(app, client):
    with app.app_context():
        create_user("admin-trusted@example.com", "pass12345", role="admin")
        db.session.add(
            NewsletterSubscriber(full_name="Trusted", email="trusted@example.com", is_trusted=True)
        )
        db.session.add(
            NewsletterSubscriber(full_name="Untrusted", email="untrusted@example.com", is_trusted=False)
        )
        db.session.commit()

    login(client, "admin-trusted@example.com", "pass12345")

    response = client.post(
        "/admin/updates",
        data={
            "title": "Trusted Broadcast",
            "message": "Trusted audience only.",
            "broadcast_subscribers": "yes",
            "channel_email": "yes",
            "schedule_type": "immediate",
        },
        follow_redirects=False,
    )
    assert response.status_code in (301, 302)

    with app.app_context():
        update = SiteUpdate.query.filter_by(title="Trusted Broadcast").first()
        assert update is not None
        deliveries = SiteUpdateDelivery.query.filter_by(site_update_id=update.id).all()
        assert len(deliveries) == 1
        assert deliveries[0].recipient_email == "trusted@example.com"


def test_updates_page_shows_global_pending_queue_warning(app, client):
    with app.app_context():
        create_user("admin-global-pending@example.com", "pass12345", role="admin")

        # Create enough records to push the pending one beyond page 1
        for i in range(12):
            db.session.add(
                SiteUpdate(
                    title=f"Global {i}",
                    message="Content",
                    broadcast_requested=False,
                    send_email=True,
                    broadcast_pending_count=0,
                )
            )

        db.session.add(
            SiteUpdate(
                title="Pending Off Page",
                message="Pending queue item",
                broadcast_requested=True,
                send_email=True,
                broadcast_pending_count=3,
                created_at=datetime(2000, 1, 1),
            )
        )
        db.session.commit()

    login(client, "admin-global-pending@example.com", "pass12345")
    first_page = client.get("/admin/updates?page=1")

    assert first_page.status_code == 200
    assert b"Broadcast Queue Pending" in first_page.data


def test_admin_can_process_queue_manually(app, client, monkeypatch):
    with app.app_context():
        create_user("admin-manual-queue@example.com", "pass12345", role="admin")
        update = SiteUpdate(
            title="Manual Queue",
            message="Process without cron.",
            broadcast_requested=True,
            send_email=True,
            created_by_user_id=User.query.filter_by(email="admin-manual-queue@example.com").first().id,
            broadcast_pending_count=1,
        )
        db.session.add(update)
        db.session.flush()
        db.session.add(
            SiteUpdateDelivery(
                site_update_id=update.id,
                recipient_name="Queue User",
                recipient_email="queue@example.com",
                channel="email",
                status="pending",
            )
        )
        db.session.commit()
        update_id = update.id

    def fake_send_email(to_email, subject, text_body, html_body=None):
        return True

    monkeypatch.setattr("app.services.broadcasts.send_email", fake_send_email)

    login(client, "admin-manual-queue@example.com", "pass12345")
    response = client.post(
        "/admin/updates/process-queue",
        data={"return_to": "/admin/updates?page=1"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/admin/updates?page=1" in response.location

    with app.app_context():
        refreshed = db.session.get(SiteUpdate, update_id)
        assert refreshed.broadcast_pending_count == 0
        assert refreshed.broadcast_success_count == 1
        assert refreshed.broadcast_failure_count == 0


def test_non_admin_cannot_process_queue_manually(app, client):
    with app.app_context():
        create_user("client-manual-queue@example.com", "pass12345", role="client")

    login(client, "client-manual-queue@example.com", "pass12345")
    response = client.post("/admin/updates/process-queue")
    assert response.status_code == 403
