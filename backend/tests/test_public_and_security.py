from datetime import date, timedelta


def test_public_home_route(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_security_headers_present(client):
    response = client.get("/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers


def test_404_template_used(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data


def test_booking_confirmation_requires_signed_token(app, client, monkeypatch):
    # Isolate from external notifications during booking creation.
    from app.routes import public as public_routes

    monkeypatch.setattr(public_routes, "_notify_support", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(public_routes, "_send_booking_whatsapp_confirmation", lambda *_args, **_kwargs: True)

    tomorrow = date.today() + timedelta(days=1)
    response = client.post(
        "/book-consultation",
        data={
            "full_name": "Token Test",
            "email": "token@example.com",
            "phone": "+254700000001",
            "service_interest": "Tax Services",
            "preferred_date": tomorrow.strftime("%Y-%m-%d"),
            "preferred_time": "10:30",
            "notes": "Token security test",
        },
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/book-consultation/confirmation/" in response.location

    valid_page = client.get(response.location, follow_redirects=False)
    assert valid_page.status_code == 200
    assert b"Token Test" in valid_page.data

    invalid_page = client.get("/book-consultation/confirmation/1", follow_redirects=False)
    assert invalid_page.status_code in (301, 302)
    assert "/book-consultation" in invalid_page.location


