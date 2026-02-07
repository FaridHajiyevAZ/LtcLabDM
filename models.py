import uuid
from datetime import datetime, timezone, timedelta

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


def _generate_uuid():
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(
        db.String(32), unique=True, nullable=False, default=_generate_uuid
    )
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="customer"
    )  # customer | admin
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    consent_accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    registrations = db.relationship(
        "ProductRegistration", backref="owner", lazy="dynamic",
        foreign_keys="ProductRegistration.user_id",
    )
    tickets = db.relationship(
        "SupportTicket", backref="customer", lazy="dynamic",
        foreign_keys="SupportTicket.user_id",
    )
    otp_codes = db.relationship(
        "OTPCode", backref="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email or self.phone}>"


# ---------------------------------------------------------------------------
# Mattress Model Catalog
# ---------------------------------------------------------------------------
class MattressModel(db.Model):
    __tablename__ = "mattress_models"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)
    warranty_months = db.Column(db.Integer, nullable=False, default=120)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )

    registrations = db.relationship(
        "ProductRegistration", backref="mattress_model", lazy="dynamic"
    )

    def __repr__(self):
        return f"<MattressModel {self.name}>"


# ---------------------------------------------------------------------------
# Product Registration (Warranty Activation)
# ---------------------------------------------------------------------------
class ProductRegistration(db.Model):
    __tablename__ = "product_registrations"

    id = db.Column(db.Integer, primary_key=True)
    reference_code = db.Column(
        db.String(32), unique=True, nullable=False, default=_generate_uuid
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    model_id = db.Column(
        db.Integer, db.ForeignKey("mattress_models.id"), nullable=False
    )
    serial_number = db.Column(db.String(100), nullable=True, index=True)
    purchase_source = db.Column(db.String(255), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)

    # Warranty
    warranty_status = db.Column(
        db.String(20), nullable=False, default="pending_review"
    )  # pending_review | active | rejected | expired
    warranty_start = db.Column(db.Date, nullable=True)
    warranty_end = db.Column(db.Date, nullable=True)

    # Customer confirmations
    undamaged_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    accuracy_confirmed = db.Column(db.Boolean, default=False, nullable=False)

    # Admin review
    reviewed_by = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    admin_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Fraud flags
    is_flagged = db.Column(db.Boolean, default=False, nullable=False)
    flag_reason = db.Column(db.String(500), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    photos = db.relationship(
        "RegistrationPhoto", backref="registration", cascade="all, delete-orphan"
    )
    reviewer = db.relationship(
        "User", foreign_keys=[reviewed_by], backref="reviewed_registrations"
    )
    tickets = db.relationship(
        "SupportTicket", backref="registration", lazy="dynamic"
    )

    def activate_warranty(self, warranty_months=None):
        """Activate warranty with calculated end date."""
        from flask import current_app

        months = warranty_months or self.mattress_model.warranty_months
        if months is None:
            months = current_app.config.get("DEFAULT_WARRANTY_MONTHS", 120)
        self.warranty_status = "active"
        self.warranty_start = self.purchase_date
        self.warranty_end = self.purchase_date + timedelta(days=months * 30)

    @property
    def is_warranty_active(self):
        if self.warranty_status != "active":
            return False
        today = datetime.now(timezone.utc).date()
        return self.warranty_start <= today <= self.warranty_end

    @property
    def warranty_days_remaining(self):
        if not self.is_warranty_active:
            return 0
        today = datetime.now(timezone.utc).date()
        return max(0, (self.warranty_end - today).days)

    def __repr__(self):
        return f"<ProductRegistration {self.reference_code}>"


# ---------------------------------------------------------------------------
# Registration Photos
# ---------------------------------------------------------------------------
class RegistrationPhoto(db.Model):
    __tablename__ = "registration_photos"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey("product_registrations.id"),
        nullable=False,
        index=True,
    )
    photo_type = db.Column(
        db.String(30), nullable=False
    )  # label | invoice | additional
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True, index=True)  # SHA-256
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self):
        return f"<RegistrationPhoto {self.photo_type}:{self.original_filename}>"


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------
class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(
        db.String(32), unique=True, nullable=False, default=_generate_uuid
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey("product_registrations.id"),
        nullable=True,
        index=True,
    )
    subject = db.Column(db.String(300), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="open"
    )  # open | in_progress | resolved
    priority = db.Column(
        db.String(20), nullable=False, default="normal"
    )  # low | normal | high | urgent
    category = db.Column(db.String(50), nullable=True)
    admin_tags = db.Column(db.String(500), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    messages = db.relationship(
        "TicketMessage", backref="ticket", cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )

    def __repr__(self):
        return f"<SupportTicket {self.ticket_number}>"


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("support_tickets.id"), nullable=False, index=True
    )
    sender_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )

    sender = db.relationship("User", foreign_keys=[sender_id])
    attachments = db.relationship(
        "TicketAttachment", backref="message", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<TicketMessage ticket={self.ticket_id}>"


class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("ticket_messages.id"), nullable=False, index=True
    )
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )


# ---------------------------------------------------------------------------
# OTP Codes
# ---------------------------------------------------------------------------
class OTPCode(db.Model):
    __tablename__ = "otp_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(
        db.String(30), nullable=False
    )  # email_verify | phone_verify | login | password_reset
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )

    @property
    def is_expired(self):
        now = _utcnow()
        expires = self.expires_at
        # Handle SQLite returning naive datetimes
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user = db.relationship("User", foreign_keys=[user_id])
