from datetime import date

from models import (
    db,
    User,
    MattressModel,
    ProductRegistration,
    SupportTicket,
    TicketMessage,
)


class TestAdminDashboard:
    def test_dashboard_requires_admin(self, client):
        resp = client.get("/admin/dashboard", follow_redirects=True)
        assert b"Log In" in resp.data or b"log in" in resp.data.lower()

    def test_dashboard_accessible(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/dashboard")
        assert resp.status_code == 200
        assert b"Admin Dashboard" in resp.data


class TestRegistrationManagement:
    def test_list_registrations(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/registrations")
        assert resp.status_code == 200
        assert b"Product Registrations" in resp.data

    def test_filter_registrations(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/registrations?status=pending_review")
        assert resp.status_code == 200

    def test_approve_registration(
        self, logged_in_admin, app, sample_customer, sample_model
    ):
        with app.app_context():
            reg = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                purchase_source="Store A",
                purchase_date=date(2025, 6, 1),
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg)
            db.session.commit()
            reg_id = reg.id

        resp = logged_in_admin.post(
            f"/admin/registrations/{reg_id}/approve",
            data={"admin_notes": "Looks good"},
            follow_redirects=True,
        )
        assert b"approved" in resp.data.lower() or b"Warranty approved" in resp.data

        with app.app_context():
            reg = db.session.get(ProductRegistration, reg_id)
            assert reg.warranty_status == "active"
            assert reg.warranty_start is not None
            assert reg.warranty_end is not None

    def test_reject_registration(
        self, logged_in_admin, app, sample_customer, sample_model
    ):
        with app.app_context():
            reg = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                purchase_source="Store B",
                purchase_date=date(2025, 6, 1),
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg)
            db.session.commit()
            reg_id = reg.id

        resp = logged_in_admin.post(
            f"/admin/registrations/{reg_id}/reject",
            data={"admin_notes": "Invalid invoice"},
            follow_redirects=True,
        )
        assert b"rejected" in resp.data.lower()

        with app.app_context():
            reg = db.session.get(ProductRegistration, reg_id)
            assert reg.warranty_status == "rejected"


class TestTicketManagement:
    def test_list_tickets(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/tickets")
        assert resp.status_code == 200
        assert b"Support Tickets" in resp.data

    def test_view_ticket(self, logged_in_admin, app, sample_customer):
        with app.app_context():
            ticket = SupportTicket(
                user_id=sample_customer.id,
                subject="Test Ticket",
                category="general",
            )
            db.session.add(ticket)
            db.session.flush()
            msg = TicketMessage(
                ticket_id=ticket.id,
                sender_id=sample_customer.id,
                body="Help me please",
            )
            db.session.add(msg)
            db.session.commit()
            ticket_id = ticket.id

        resp = logged_in_admin.get(f"/admin/tickets/{ticket_id}")
        assert resp.status_code == 200
        assert b"Test Ticket" in resp.data
        assert b"Help me please" in resp.data


class TestCustomerManagement:
    def test_list_customers(self, logged_in_admin, sample_customer):
        resp = logged_in_admin.get("/admin/customers")
        assert resp.status_code == 200
        assert b"Customers" in resp.data

    def test_search_customers(self, logged_in_admin, sample_customer):
        resp = logged_in_admin.get("/admin/customers?search=Test")
        assert resp.status_code == 200
        assert b"Test Customer" in resp.data

    def test_view_customer(self, logged_in_admin, sample_customer):
        resp = logged_in_admin.get(f"/admin/customers/{sample_customer.id}")
        assert resp.status_code == 200
        assert b"Test Customer" in resp.data


class TestModelManagement:
    def test_manage_models_page(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/models")
        assert resp.status_code == 200
        assert b"Mattress Models" in resp.data

    def test_add_model(self, logged_in_admin, app):
        resp = logged_in_admin.post(
            "/admin/models",
            data={
                "name": "New Model XYZ",
                "sku": "NM-XYZ-001",
                "warranty_months": "60",
            },
            follow_redirects=True,
        )
        assert b"New Model XYZ" in resp.data

        with app.app_context():
            model = MattressModel.query.filter_by(name="New Model XYZ").first()
            assert model is not None
            assert model.warranty_months == 60

    def test_add_duplicate_model(self, logged_in_admin, sample_model):
        resp = logged_in_admin.post(
            "/admin/models",
            data={
                "name": "Test Mattress Premium",
                "warranty_months": "60",
            },
            follow_redirects=True,
        )
        assert b"already exists" in resp.data


class TestFraudAlerts:
    def test_fraud_alerts_page(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/fraud-alerts")
        assert resp.status_code == 200
        assert b"Fraud Alerts" in resp.data


class TestAuditLog:
    def test_audit_log_page(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/audit-log")
        assert resp.status_code == 200
        assert b"Audit Log" in resp.data


class TestAdminAccessControl:
    def test_admin_routes_require_admin_role(self, logged_in_customer):
        admin_urls = [
            "/admin/dashboard",
            "/admin/registrations",
            "/admin/tickets",
            "/admin/customers",
            "/admin/models",
            "/admin/fraud-alerts",
            "/admin/audit-log",
        ]
        for url in admin_urls:
            resp = logged_in_customer.get(url, follow_redirects=True)
            assert resp.status_code == 200
            assert b"Access denied" in resp.data or b"Log In" in resp.data, \
                f"Customer should not access {url}"
