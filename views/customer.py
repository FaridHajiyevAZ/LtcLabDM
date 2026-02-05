from datetime import datetime, timezone

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    send_from_directory,
)

from models import (
    db,
    User,
    MattressModel,
    ProductRegistration,
    RegistrationPhoto,
    SupportTicket,
    TicketMessage,
    TicketAttachment,
    AuditLog,
)
from auth import customer_required, get_current_user
from services.upload import save_upload
from services.fraud import check_duplicate_invoice, check_duplicate_serial, flag_registration

customer_bp = Blueprint("customer", __name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@customer_bp.route("/dashboard")
@customer_required
def dashboard():
    user = get_current_user()
    registrations = (
        user.registrations.order_by(ProductRegistration.created_at.desc()).all()
    )
    open_tickets = user.tickets.filter(
        SupportTicket.status.in_(["open", "in_progress"])
    ).count()
    return render_template(
        "customer/dashboard.html",
        user=user,
        registrations=registrations,
        open_tickets=open_tickets,
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@customer_bp.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():
    user = get_current_user()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()

        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("customer/profile.html", user=user)

        user.full_name = full_name
        if phone:
            normalized = "".join(c for c in phone if c.isdigit() or c == "+")
            existing = User.query.filter(
                User.phone == normalized, User.id != user.id
            ).first()
            if existing:
                flash("This phone number is already in use.", "danger")
                return render_template("customer/profile.html", user=user)
            user.phone = normalized

        db.session.commit()
        session["full_name"] = user.full_name
        flash("Profile updated.", "success")
        return redirect(url_for("customer.profile"))

    return render_template("customer/profile.html", user=user)


# ---------------------------------------------------------------------------
# Product Registration (Warranty Activation)
# ---------------------------------------------------------------------------
@customer_bp.route("/products/register", methods=["GET", "POST"])
@customer_required
def register_product():
    models = MattressModel.query.filter_by(is_active=True).order_by(
        MattressModel.name
    ).all()

    if request.method == "POST":
        user = get_current_user()

        model_id = request.form.get("model_id", type=int)
        serial_number = request.form.get("serial_number", "").strip() or None
        purchase_source = request.form.get("purchase_source", "").strip()
        purchase_date_str = request.form.get("purchase_date", "")
        undamaged = request.form.get("undamaged_confirmed")
        accuracy = request.form.get("accuracy_confirmed")

        errors = []

        # Validate model
        mattress = db.session.get(MattressModel, model_id) if model_id else None
        if not mattress or not mattress.is_active:
            errors.append("Please select a valid mattress model.")

        if not purchase_source:
            errors.append("Purchase source is required.")

        # Validate date
        purchase_date = None
        try:
            purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            if purchase_date > today:
                errors.append("Purchase date cannot be in the future.")
        except (ValueError, TypeError):
            errors.append("Valid purchase date is required.")

        if not undamaged:
            errors.append("You must confirm the product was received undamaged.")
        if not accuracy:
            errors.append("You must confirm the information is accurate.")

        # Validate photos
        label_photo = request.files.get("label_photo")
        invoice_photo = request.files.get("invoice_photo")

        if not label_photo or not label_photo.filename:
            errors.append("Mattress label photo is required.")
        if not invoice_photo or not invoice_photo.filename:
            errors.append("Invoice / proof of purchase photo is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "customer/register_product.html", models=models
            )

        # Save photos
        try:
            label_path, label_orig, label_hash, label_size = save_upload(
                label_photo, subfolder="labels"
            )
            invoice_path, invoice_orig, invoice_hash, invoice_size = save_upload(
                invoice_photo, subfolder="invoices"
            )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template(
                "customer/register_product.html", models=models
            )

        # Create registration
        reg = ProductRegistration(
            user_id=user.id,
            model_id=model_id,
            serial_number=serial_number,
            purchase_source=purchase_source,
            purchase_date=purchase_date,
            undamaged_confirmed=True,
            accuracy_confirmed=True,
            warranty_status="pending_review",
        )
        db.session.add(reg)
        db.session.flush()  # Get reg.id

        # Attach photos
        db.session.add(
            RegistrationPhoto(
                registration_id=reg.id,
                photo_type="label",
                file_path=label_path,
                original_filename=label_orig,
                file_hash=label_hash,
                file_size=label_size,
            )
        )
        db.session.add(
            RegistrationPhoto(
                registration_id=reg.id,
                photo_type="invoice",
                file_path=invoice_path,
                original_filename=invoice_orig,
                file_hash=invoice_hash,
                file_size=invoice_size,
            )
        )

        # Fraud checks
        dup_invoice = check_duplicate_invoice(invoice_hash, reg.id)
        if dup_invoice:
            flag_registration(reg, f"Duplicate invoice hash matches registration #{dup_invoice.registration_id}")

        dup_serial = check_duplicate_serial(serial_number, reg.id)
        if dup_serial:
            flag_registration(reg, f"Duplicate serial number matches registration #{dup_serial.id}")

        # Check purchase date age
        if purchase_date:
            age_days = (datetime.now(timezone.utc).date() - purchase_date).days
            flag_days = current_app.config.get("MAX_PURCHASE_AGE_DAYS_FLAG", 90)
            if age_days > flag_days:
                flag_registration(reg, f"Purchase date is {age_days} days ago (>{flag_days}d threshold)")

        db.session.commit()

        # Audit
        audit = AuditLog(
            user_id=user.id,
            action="product_registered",
            entity_type="product_registration",
            entity_id=reg.id,
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        flash(
            "Product registered successfully! Your warranty is pending review.",
            "success",
        )
        return redirect(url_for("customer.view_product", product_id=reg.id))

    return render_template("customer/register_product.html", models=models)


# ---------------------------------------------------------------------------
# Product List & Detail
# ---------------------------------------------------------------------------
@customer_bp.route("/products")
@customer_required
def list_products():
    user = get_current_user()
    registrations = (
        user.registrations.order_by(ProductRegistration.created_at.desc()).all()
    )
    return render_template(
        "customer/products.html", registrations=registrations
    )


@customer_bp.route("/products/<int:product_id>")
@customer_required
def view_product(product_id):
    user = get_current_user()
    reg = ProductRegistration.query.filter_by(
        id=product_id, user_id=user.id
    ).first_or_404()
    return render_template("customer/product_detail.html", reg=reg)


@customer_bp.route("/products/<int:product_id>/photos", methods=["POST"])
@customer_required
def upload_additional_photo(product_id):
    user = get_current_user()
    reg = ProductRegistration.query.filter_by(
        id=product_id, user_id=user.id
    ).first_or_404()

    photo = request.files.get("photo")
    if not photo or not photo.filename:
        flash("Please select a photo to upload.", "danger")
        return redirect(url_for("customer.view_product", product_id=product_id))

    try:
        path, orig, content_hash, size = save_upload(photo, subfolder="additional")
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("customer.view_product", product_id=product_id))

    db.session.add(
        RegistrationPhoto(
            registration_id=reg.id,
            photo_type="additional",
            file_path=path,
            original_filename=orig,
            file_hash=content_hash,
            file_size=size,
        )
    )
    db.session.commit()
    flash("Photo uploaded successfully.", "success")
    return redirect(url_for("customer.view_product", product_id=product_id))


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------
@customer_bp.route("/support")
@customer_required
def list_tickets():
    user = get_current_user()
    tickets = user.tickets.order_by(SupportTicket.updated_at.desc()).all()
    return render_template("customer/tickets.html", tickets=tickets)


@customer_bp.route("/support/new", methods=["GET", "POST"])
@customer_required
def new_ticket():
    user = get_current_user()
    registrations = user.registrations.all()

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        category = request.form.get("category", "general")
        body = request.form.get("body", "").strip()
        registration_id = request.form.get("registration_id", type=int)

        errors = []
        if not subject:
            errors.append("Subject is required.")
        if not body:
            errors.append("Message is required.")

        if registration_id:
            reg = ProductRegistration.query.filter_by(
                id=registration_id, user_id=user.id
            ).first()
            if not reg:
                errors.append("Invalid product selection.")
                registration_id = None

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "customer/new_ticket.html", registrations=registrations
            )

        ticket = SupportTicket(
            user_id=user.id,
            registration_id=registration_id or None,
            subject=subject,
            category=category,
            status="open",
        )
        db.session.add(ticket)
        db.session.flush()

        message = TicketMessage(
            ticket_id=ticket.id,
            sender_id=user.id,
            body=body,
        )
        db.session.add(message)
        db.session.flush()

        # Handle attachment
        attachment = request.files.get("attachment")
        if attachment and attachment.filename:
            try:
                path, orig, _, size = save_upload(
                    attachment, subfolder="ticket_attachments"
                )
                db.session.add(
                    TicketAttachment(
                        message_id=message.id,
                        file_path=path,
                        original_filename=orig,
                        file_size=size,
                    )
                )
            except ValueError as e:
                flash(f"Attachment error: {e}", "warning")

        db.session.commit()
        flash("Support ticket created.", "success")
        return redirect(url_for("customer.view_ticket", ticket_id=ticket.id))

    return render_template(
        "customer/new_ticket.html", registrations=registrations
    )


@customer_bp.route("/support/<int:ticket_id>")
@customer_required
def view_ticket(ticket_id):
    user = get_current_user()
    ticket = SupportTicket.query.filter_by(
        id=ticket_id, user_id=user.id
    ).first_or_404()
    return render_template("customer/ticket_detail.html", ticket=ticket)


@customer_bp.route("/support/<int:ticket_id>/reply", methods=["POST"])
@customer_required
def reply_ticket(ticket_id):
    user = get_current_user()
    ticket = SupportTicket.query.filter_by(
        id=ticket_id, user_id=user.id
    ).first_or_404()

    body = request.form.get("body", "").strip()
    if not body:
        flash("Reply cannot be empty.", "danger")
        return redirect(url_for("customer.view_ticket", ticket_id=ticket_id))

    if ticket.status == "resolved":
        # Reopen ticket on customer reply
        ticket.status = "open"

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=user.id,
        body=body,
    )
    db.session.add(message)
    db.session.flush()

    attachment = request.files.get("attachment")
    if attachment and attachment.filename:
        try:
            path, orig, _, size = save_upload(
                attachment, subfolder="ticket_attachments"
            )
            db.session.add(
                TicketAttachment(
                    message_id=message.id,
                    file_path=path,
                    original_filename=orig,
                    file_size=size,
                )
            )
        except ValueError as e:
            flash(f"Attachment error: {e}", "warning")

    db.session.commit()
    flash("Reply sent.", "success")
    return redirect(url_for("customer.view_ticket", ticket_id=ticket_id))


# ---------------------------------------------------------------------------
# Serve uploads (development only; use nginx/S3 in production)
# ---------------------------------------------------------------------------
@customer_bp.route("/uploads/<path:filename>")
@customer_required
def serve_upload(filename):
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    return send_from_directory(upload_folder, filename)
