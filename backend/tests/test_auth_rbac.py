from app.models import User, db
from app.routes import auth as auth_routes


def create_user(email, password, role="client"):
    user = User(email=email, role=role, email_confirmed=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def create_2fa_user(email, password, role="client"):
    user = User(
        email=email,
        role=role,
        email_confirmed=True,
        two_factor_enabled=True,
        two_factor_secret="JBSWY3DPEHPK3PXP",
    )
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


def test_admin_login_redirects_to_admin_dashboard(app, client):
    with app.app_context():
        create_user("adminredirect@example.com", "pass12345", role="admin")

    response = client.post(
        "/auth/login",
        data={"email": "adminredirect@example.com", "password": "pass12345"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/admin/dashboard" in response.location


def test_admin_2fa_login_redirects_to_admin_dashboard(app, client, monkeypatch):
    with app.app_context():
        admin = create_2fa_user("admin2fa@example.com", "pass12345", role="admin")
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["pending_2fa_user_id"] = admin_id

    monkeypatch.setattr(auth_routes, "_verify_pending_sms_otp", lambda _code: True)

    response = client.post(
        "/auth/2fa",
        data={"otp_code": "123456"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/admin/dashboard" in response.location


def test_login_redirects_to_2fa_when_enabled(app, client):
    with app.app_context():
        create_2fa_user("secure@example.com", "pass12345", role="client")

    response = client.post(
        "/auth/login",
        data={"email": "secure@example.com", "password": "pass12345"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/auth/2fa" in response.location


def test_2fa_verify_route_requires_pending_session(client):
    response = client.get("/auth/2fa", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.location


def test_unconfirmed_user_cannot_sign_in(app, client):
    with app.app_context():
        user = User(email="newuser@example.com", role="client", email_confirmed=False)
        user.set_password("pass12345")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={"email": "newuser@example.com", "password": "pass12345"},
        follow_redirects=False,
    )
    assert response.status_code in (301, 302)
    assert "/auth/resend-confirmation" in response.location


def test_confirm_email_route_marks_user_confirmed(app, client):
    with app.app_context():
        user = User(email="confirmme@example.com", role="client", email_confirmed=False)
        user.set_password("pass12345")
        db.session.add(user)
        db.session.commit()
        token = auth_routes._generate_token(user.email, "confirm_email")

    response = client.get(f"/auth/confirm-email/{token}", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.location

    with app.app_context():
        user = User.query.filter_by(email="confirmme@example.com").first()
        assert user is not None
        assert user.email_confirmed is True


def test_password_reset_updates_password(app, client):
    with app.app_context():
        user = User(email="resetme@example.com", role="client", email_confirmed=True)
        user.set_password("oldpassword123")
        db.session.add(user)
        db.session.commit()
        token = auth_routes._generate_token(user.email, "password_reset")

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "newpassword123", "confirm_password": "newpassword123"},
        follow_redirects=False,
    )
    assert response.status_code in (301, 302)
    assert "/auth/login" in response.location

    login = client.post(
        "/auth/login",
        data={"email": "resetme@example.com", "password": "newpassword123"},
        follow_redirects=False,
    )
    assert login.status_code in (301, 302)


def test_client_login_redirects_to_client_dashboard(app, client):
    with app.app_context():
        create_user("clientredirect@example.com", "pass12345", role="client")

    response = client.post(
        "/auth/login",
        data={"email": "clientredirect@example.com", "password": "pass12345"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/client/dashboard" in response.location


def test_authenticated_user_sees_2fa_security_link(app, client):
    with app.app_context():
        create_user("twofalink@example.com", "pass12345", role="client")

    login = client.post(
        "/auth/login",
        data={"email": "twofalink@example.com", "password": "pass12345"},
        follow_redirects=False,
    )
    assert login.status_code in (301, 302)

    response = client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert b"/auth/2fa/setup" in response.data
