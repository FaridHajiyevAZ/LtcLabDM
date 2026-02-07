from datetime import date, datetime, timezone, timedelta

from models import (
    User,
    MattressModel,
    ProductRegistration,
    RegistrationPhoto,
    SupportTicket,
    TicketMessage,
    OTPCode,
    AuditLog,
    db,
)


class TestUserModel:
    def test_create_user(self, app, sample_customer):
        assert sample_customer.id is not None
        assert sample_customer.email == "customer@test.com"
        assert sample_customer.role == "customer"
        assert sample_customer.is_verified is True
        assert sample_customer.public_id is not None

    def test_password_hashing(self, app, sample_customer):
        assert sample_customer.password_hash != "password1"
        assert sample_customer.check_password("password1") is True
        assert sample_customer.check_password("wrong") is False

    def test_user_repr(self, app, sample_customer):
        assert "customer@test.com" in repr(sample_customer)

    def test_unique_public_id(self, app, db, sample_customer):
        user2 = User(
            full_name="Another User",
            email="another@test.com",
            role="customer",
            is_verified=True,
        )
        user2.set_password("password1")
        db.session.add(user2)
        db.session.commit()
        assert sample_customer.public_id != user2.public_id


class TestMattressModel:
    def test_create_model(self, app, sample_model):
        assert sample_model.id is not None
        assert sample_model.name == "Test Mattress Premium"
        assert sample_model.warranty_months == 120
        assert sample_model.is_active is True


class TestProductRegistration:
    def test_create_registration(self, app, db, sample_customer, sample_model):
        reg = ProductRegistration(
            user_id=sample_customer.id,
            model_id=sample_model.id,
            purchase_source="Test Store",
            purchase_date=date(2025, 1, 15),
            undamaged_confirmed=True,
            accuracy_confirmed=True,
        )
        db.session.add(reg)
        db.session.commit()

        assert reg.id is not None
        assert reg.reference_code is not None
        assert reg.warranty_status == "pending_review"
        assert reg.owner == sample_customer

    def test_activate_warranty(self, app, db, sample_customer, sample_model):
        reg = ProductRegistration(
            user_id=sample_customer.id,
            model_id=sample_model.id,
            purchase_source="Test Store",
            purchase_date=date(2025, 1, 15),
            undamaged_confirmed=True,
            accuracy_confirmed=True,
        )
        db.session.add(reg)
        db.session.commit()

        with app.app_context():
            reg.activate_warranty()
            db.session.commit()

        assert reg.warranty_status == "active"
        assert reg.warranty_start == date(2025, 1, 15)
        assert reg.warranty_end is not None

    def test_warranty_days_remaining(self, app, db, sample_customer, sample_model):
        today = datetime.now(timezone.utc).date()
        reg = ProductRegistration(
            user_id=sample_customer.id,
            model_id=sample_model.id,
            purchase_source="Test Store",
            purchase_date=today - timedelta(days=30),
            warranty_status="active",
            warranty_start=today - timedelta(days=30),
            warranty_end=today + timedelta(days=335),
            undamaged_confirmed=True,
            accuracy_confirmed=True,
        )
        db.session.add(reg)
        db.session.commit()

        assert reg.is_warranty_active is True
        assert reg.warranty_days_remaining > 0

    def test_expired_warranty(self, app, db, sample_customer, sample_model):
        reg = ProductRegistration(
            user_id=sample_customer.id,
            model_id=sample_model.id,
            purchase_source="Test Store",
            purchase_date=date(2015, 1, 1),
            warranty_status="active",
            warranty_start=date(2015, 1, 1),
            warranty_end=date(2020, 1, 1),
            undamaged_confirmed=True,
            accuracy_confirmed=True,
        )
        db.session.add(reg)
        db.session.commit()

        assert reg.is_warranty_active is False
        assert reg.warranty_days_remaining == 0


class TestSupportTicket:
    def test_create_ticket(self, app, db, sample_customer):
        ticket = SupportTicket(
            user_id=sample_customer.id,
            subject="Test Issue",
            category="general",
        )
        db.session.add(ticket)
        db.session.commit()

        assert ticket.id is not None
        assert ticket.ticket_number is not None
        assert ticket.status == "open"

    def test_add_message(self, app, db, sample_customer):
        ticket = SupportTicket(
            user_id=sample_customer.id,
            subject="Test Issue",
            category="general",
        )
        db.session.add(ticket)
        db.session.flush()

        msg = TicketMessage(
            ticket_id=ticket.id,
            sender_id=sample_customer.id,
            body="This is a test message.",
        )
        db.session.add(msg)
        db.session.commit()

        assert len(ticket.messages) == 1
        assert ticket.messages[0].body == "This is a test message."


class TestOTPCode:
    def test_create_otp(self, app, db, sample_customer):
        otp = OTPCode(
            user_id=sample_customer.id,
            code="123456",
            purpose="email_verify",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.session.add(otp)
        db.session.commit()

        assert otp.is_valid is True
        assert otp.is_expired is False

    def test_expired_otp(self, app, db, sample_customer):
        otp = OTPCode(
            user_id=sample_customer.id,
            code="123456",
            purpose="email_verify",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.session.add(otp)
        db.session.commit()

        assert otp.is_expired is True
        assert otp.is_valid is False

    def test_used_otp(self, app, db, sample_customer):
        otp = OTPCode(
            user_id=sample_customer.id,
            code="123456",
            purpose="email_verify",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            is_used=True,
        )
        db.session.add(otp)
        db.session.commit()

        assert otp.is_valid is False
