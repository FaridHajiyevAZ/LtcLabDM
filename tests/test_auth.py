from models import User, db


class TestRegistration:
    def test_register_page_loads(self, client):
        resp = client.get("/auth/register")
        assert resp.status_code == 200
        assert b"Create Account" in resp.data

    def test_register_success(self, client, app):
        resp = client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "email": "newuser@test.com",
                "password": "password1",
                "password_confirm": "password1",
                "consent": "on",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302  # Redirect to verify email

        with app.app_context():
            user = User.query.filter_by(email="newuser@test.com").first()
            assert user is not None
            assert user.full_name == "New User"
            assert user.is_verified is False

    def test_register_duplicate_email(self, client, sample_customer):
        resp = client.post(
            "/auth/register",
            data={
                "full_name": "Duplicate",
                "email": "customer@test.com",
                "password": "password1",
                "password_confirm": "password1",
                "consent": "on",
            },
            follow_redirects=True,
        )
        assert b"already exists" in resp.data

    def test_register_password_mismatch(self, client):
        resp = client.post(
            "/auth/register",
            data={
                "full_name": "Test",
                "email": "mismatch@test.com",
                "password": "password1",
                "password_confirm": "different1",
                "consent": "on",
            },
            follow_redirects=True,
        )
        assert b"do not match" in resp.data

    def test_register_weak_password(self, client):
        resp = client.post(
            "/auth/register",
            data={
                "full_name": "Test",
                "email": "weak@test.com",
                "password": "short",
                "password_confirm": "short",
                "consent": "on",
            },
            follow_redirects=True,
        )
        assert b"at least 8" in resp.data

    def test_register_no_contact(self, client):
        resp = client.post(
            "/auth/register",
            data={
                "full_name": "Test",
                "password": "password1",
                "password_confirm": "password1",
                "consent": "on",
            },
            follow_redirects=True,
        )
        assert b"Email or phone" in resp.data


class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        assert b"Log In" in resp.data

    def test_login_success(self, client, sample_customer):
        resp = client.post(
            "/auth/login",
            data={
                "identifier": "customer@test.com",
                "password": "password1",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302  # Redirect to dashboard

    def test_login_wrong_password(self, client, sample_customer):
        resp = client.post(
            "/auth/login",
            data={
                "identifier": "customer@test.com",
                "password": "wrongpass",
            },
            follow_redirects=True,
        )
        assert b"Invalid credentials" in resp.data

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login",
            data={
                "identifier": "nobody@test.com",
                "password": "password1",
            },
            follow_redirects=True,
        )
        assert b"Invalid credentials" in resp.data

    def test_login_unverified_user(self, client, app, db):
        user = User(
            full_name="Unverified",
            email="unverified@test.com",
            role="customer",
            is_verified=False,
        )
        user.set_password("password1")
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/auth/login",
            data={
                "identifier": "unverified@test.com",
                "password": "password1",
            },
            follow_redirects=True,
        )
        assert b"verify" in resp.data.lower()


class TestLogout:
    def test_logout(self, logged_in_customer):
        resp = logged_in_customer.post("/auth/logout", follow_redirects=True)
        assert b"Log In" in resp.data


class TestAdminLogin:
    def test_admin_login_page(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b"Admin Login" in resp.data

    def test_admin_login_success(self, client, sample_admin):
        resp = client.post(
            "/admin/login",
            data={
                "identifier": "admin@test.com",
                "password": "adminpass1",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_admin_login_wrong_credentials(self, client, sample_admin):
        resp = client.post(
            "/admin/login",
            data={
                "identifier": "admin@test.com",
                "password": "wrongpass",
            },
            follow_redirects=True,
        )
        assert b"Invalid admin credentials" in resp.data


class TestPasswordReset:
    def test_forgot_password_page(self, client):
        resp = client.get("/auth/forgot-password")
        assert resp.status_code == 200
        assert b"Forgot Password" in resp.data

    def test_forgot_password_submit(self, client, sample_customer):
        resp = client.post(
            "/auth/forgot-password",
            data={"identifier": "customer@test.com"},
            follow_redirects=True,
        )
        assert b"reset code" in resp.data.lower()
