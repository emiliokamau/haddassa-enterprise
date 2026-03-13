from app.models import User, db


def create_user(email, password, role="client"):
    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def test_client_dashboard_requires_login(client):
    response = client.get("/client/dashboard")
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.location


def test_admin_dashboard_requires_login(client):
    response = client.get("/admin/dashboard")
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.location


def test_client_cannot_access_admin_dashboard(app, client):
    with app.app_context():
        create_user("client@example.com", "pass12345", role="client")

    login = client.post(
        "/auth/login",
        data={"email": "client@example.com", "password": "pass12345"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    response = client.get("/admin/dashboard")
    assert response.status_code == 403


def test_admin_can_access_admin_dashboard(app, client):
    with app.app_context():
        create_user("admin@example.com", "pass12345", role="admin")

    login = client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "pass12345"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    response = client.get("/admin/dashboard")
    assert response.status_code == 200
