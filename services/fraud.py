from models import db, RegistrationPhoto, ProductRegistration


def check_duplicate_invoice(file_hash, exclude_registration_id=None):
    """Check if an invoice photo hash already exists in the system."""
    query = RegistrationPhoto.query.filter_by(
        file_hash=file_hash, photo_type="invoice"
    )
    if exclude_registration_id:
        query = query.filter(
            RegistrationPhoto.registration_id != exclude_registration_id
        )
    return query.first()


def check_duplicate_serial(serial_number, exclude_registration_id=None):
    """Check if a serial number is already registered."""
    if not serial_number:
        return None
    query = ProductRegistration.query.filter_by(serial_number=serial_number)
    if exclude_registration_id:
        query = query.filter(ProductRegistration.id != exclude_registration_id)
    return query.first()


def flag_registration(registration, reason):
    """Flag a registration for fraud review."""
    registration.is_flagged = True
    existing = registration.flag_reason or ""
    if existing:
        registration.flag_reason = f"{existing}; {reason}"
    else:
        registration.flag_reason = reason
    db.session.commit()


def get_fraud_indicators():
    """Return registrations that have fraud flags."""
    return (
        ProductRegistration.query.filter_by(is_flagged=True)
        .order_by(ProductRegistration.created_at.desc())
        .all()
    )
