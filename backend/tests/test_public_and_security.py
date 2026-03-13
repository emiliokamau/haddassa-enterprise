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
