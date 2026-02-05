from datetime import date

from models import db, ProductRegistration, RegistrationPhoto
from services.fraud import (
    check_duplicate_invoice,
    check_duplicate_serial,
    flag_registration,
    get_fraud_indicators,
)


class TestFraudDetection:
    def test_duplicate_invoice_detection(self, app, sample_customer, sample_model):
        with app.app_context():
            reg1 = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                purchase_source="Store A",
                purchase_date=date(2025, 1, 1),
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg1)
            db.session.flush()

            photo1 = RegistrationPhoto(
                registration_id=reg1.id,
                photo_type="invoice",
                file_path="invoices/test1.jpg",
                original_filename="invoice.jpg",
                file_hash="abc123hash",
            )
            db.session.add(photo1)
            db.session.commit()

            # Same hash should be detected
            dup = check_duplicate_invoice("abc123hash", exclude_registration_id=None)
            assert dup is not None

            # Different hash should not be detected
            no_dup = check_duplicate_invoice("different_hash")
            assert no_dup is None

            # Exclude self
            excluded = check_duplicate_invoice("abc123hash", exclude_registration_id=reg1.id)
            assert excluded is None

    def test_duplicate_serial_detection(self, app, sample_customer, sample_model):
        with app.app_context():
            reg1 = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                serial_number="SN-12345",
                purchase_source="Store A",
                purchase_date=date(2025, 1, 1),
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg1)
            db.session.commit()

            dup = check_duplicate_serial("SN-12345")
            assert dup is not None

            no_dup = check_duplicate_serial("SN-99999")
            assert no_dup is None

            no_dup_none = check_duplicate_serial(None)
            assert no_dup_none is None

    def test_flag_registration(self, app, sample_customer, sample_model):
        with app.app_context():
            reg = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                purchase_source="Store A",
                purchase_date=date(2025, 1, 1),
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg)
            db.session.commit()

            flag_registration(reg, "Duplicate invoice")
            assert reg.is_flagged is True
            assert "Duplicate invoice" in reg.flag_reason

            # Flag again with additional reason
            flag_registration(reg, "Suspicious serial")
            assert "Duplicate invoice" in reg.flag_reason
            assert "Suspicious serial" in reg.flag_reason

    def test_get_fraud_indicators(self, app, sample_customer, sample_model):
        with app.app_context():
            reg = ProductRegistration(
                user_id=sample_customer.id,
                model_id=sample_model.id,
                purchase_source="Store A",
                purchase_date=date(2025, 1, 1),
                is_flagged=True,
                flag_reason="Test flag",
                undamaged_confirmed=True,
                accuracy_confirmed=True,
            )
            db.session.add(reg)
            db.session.commit()

            flagged = get_fraud_indicators()
            assert len(flagged) >= 1
            assert flagged[0].is_flagged is True
