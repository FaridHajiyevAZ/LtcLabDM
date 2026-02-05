from models import ProductRegistration, SupportTicket, db


class TestCustomerDashboard:
    def test_dashboard_requires_login(self, client):
        resp = client.get("/dashboard", follow_redirects=True)
        assert b"Log In" in resp.data or b"log in" in resp.data.lower()

    def test_dashboard_accessible(self, logged_in_customer):
        resp = logged_in_customer.get("/dashboard")
        assert resp.status_code == 200
        assert b"Welcome" in resp.data


class TestProfile:
    def test_profile_page(self, logged_in_customer):
        resp = logged_in_customer.get("/profile")
        assert resp.status_code == 200
        assert b"My Profile" in resp.data

    def test_update_profile(self, logged_in_customer):
        resp = logged_in_customer.post(
            "/profile",
            data={"full_name": "Updated Name", "phone": "+9876543210"},
            follow_redirects=True,
        )
        assert b"Profile updated" in resp.data


class TestProductRegistration:
    def test_register_product_page_requires_login(self, client):
        resp = client.get("/products/register", follow_redirects=True)
        assert b"Log In" in resp.data or b"log in" in resp.data.lower()

    def test_register_product_page(self, logged_in_customer, sample_model):
        resp = logged_in_customer.get("/products/register")
        assert resp.status_code == 200
        assert b"Register Your Product" in resp.data
        assert b"Test Mattress Premium" in resp.data

    def test_product_list_empty(self, logged_in_customer):
        resp = logged_in_customer.get("/products")
        assert resp.status_code == 200
        assert b"No products registered" in resp.data


class TestSupportTickets:
    def test_ticket_list(self, logged_in_customer):
        resp = logged_in_customer.get("/support")
        assert resp.status_code == 200
        assert b"Support Tickets" in resp.data

    def test_new_ticket_page(self, logged_in_customer):
        resp = logged_in_customer.get("/support/new")
        assert resp.status_code == 200
        assert b"Create Support Ticket" in resp.data


class TestAccessControl:
    def test_customer_cannot_access_admin(self, logged_in_customer):
        resp = logged_in_customer.get("/admin/dashboard", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Access denied" in resp.data or b"Log In" in resp.data

    def test_unauthenticated_redirects(self, client):
        protected_urls = [
            "/dashboard",
            "/profile",
            "/products",
            "/products/register",
            "/support",
            "/support/new",
        ]
        for url in protected_urls:
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code == 302, f"{url} should redirect"
