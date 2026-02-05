from datetime import datetime, timezone

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
    current_app,
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
from auth import admin_required, get_current_user
from services.fraud import get_fraud_indicators
from services.upload import save_upload

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    total_customers = User.query.filter_by(role="customer").count()
    total_registrations = ProductRegistration.query.count()
    pending_reviews = ProductRegistration.query.filter_by(
        warranty_status="pending_review"
    ).count()
    active_warranties = ProductRegistration.query.filter_by(
        warranty_status="active"
    ).count()
    open_tickets = SupportTicket.query.filter(
        SupportTicket.status.in_(["open", "in_progress"])
    ).count()
    flagged = ProductRegistration.query.filter_by(is_flagged=True).count()

    recent_registrations = (
        ProductRegistration.query.order_by(
            ProductRegistration.created_at.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(
        "admin_panel/dashboard.html",
        total_customers=total_customers,
        total_registrations=total_registrations,
        pending_reviews=pending_reviews,
        active_warranties=active_warranties,
        open_tickets=open_tickets,
        flagged=flagged,
        recent_registrations=recent_registrations,
    )


# ---------------------------------------------------------------------------
# Product Registrations
# ---------------------------------------------------------------------------
@admin_bp.route("/registrations")
@admin_required
def list_registrations():
    status_filter = request.args.get("status", "")
    model_filter = request.args.get("model_id", "", type=str)
    source_filter = request.args.get("source", "")
    flagged_only = request.args.get("flagged", "")

    query = ProductRegistration.query

    if status_filter:
        query = query.filter_by(warranty_status=status_filter)
    if model_filter:
        query = query.filter_by(model_id=int(model_filter))
    if source_filter:
        query = query.filter(
            ProductRegistration.purchase_source.ilike(f"%{source_filter}%")
        )
    if flagged_only:
        query = query.filter_by(is_flagged=True)

    registrations = query.order_by(
        ProductRegistration.created_at.desc()
    ).all()

    models = MattressModel.query.order_by(MattressModel.name).all()

    return render_template(
        "admin_panel/registrations.html",
        registrations=registrations,
        models=models,
        status_filter=status_filter,
        model_filter=model_filter,
        source_filter=source_filter,
        flagged_only=flagged_only,
    )


@admin_bp.route("/registrations/<int:reg_id>")
@admin_required
def view_registration(reg_id):
    reg = ProductRegistration.query.get_or_404(reg_id)
    return render_template("admin_panel/registration_detail.html", reg=reg)


@admin_bp.route("/registrations/<int:reg_id>/approve", methods=["POST"])
@admin_required
def approve_registration(reg_id):
    reg = ProductRegistration.query.get_or_404(reg_id)
    admin_user = get_current_user()
    notes = request.form.get("admin_notes", "").strip()

    reg.activate_warranty()
    reg.reviewed_by = admin_user.id
    reg.reviewed_at = datetime.now(timezone.utc)
    if notes:
        reg.admin_notes = notes

    db.session.add(
        AuditLog(
            user_id=admin_user.id,
            action="warranty_approved",
            entity_type="product_registration",
            entity_id=reg.id,
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    flash(f"Warranty approved for registration {reg.reference_code}.", "success")
    return redirect(url_for("admin.view_registration", reg_id=reg_id))


@admin_bp.route("/registrations/<int:reg_id>/reject", methods=["POST"])
@admin_required
def reject_registration(reg_id):
    reg = ProductRegistration.query.get_or_404(reg_id)
    admin_user = get_current_user()
    notes = request.form.get("admin_notes", "").strip()

    reg.warranty_status = "rejected"
    reg.reviewed_by = admin_user.id
    reg.reviewed_at = datetime.now(timezone.utc)
    if notes:
        reg.admin_notes = notes

    db.session.add(
        AuditLog(
            user_id=admin_user.id,
            action="warranty_rejected",
            entity_type="product_registration",
            entity_id=reg.id,
            details={"reason": notes},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    flash(f"Registration {reg.reference_code} rejected.", "warning")
    return redirect(url_for("admin.view_registration", reg_id=reg_id))


@admin_bp.route("/registrations/<int:reg_id>/request-info", methods=["POST"])
@admin_required
def request_info(reg_id):
    reg = ProductRegistration.query.get_or_404(reg_id)
    admin_user = get_current_user()
    notes = request.form.get("admin_notes", "").strip()

    if notes:
        existing = reg.admin_notes or ""
        reg.admin_notes = (
            f"{existing}\n[INFO REQUEST] {notes}" if existing else f"[INFO REQUEST] {notes}"
        )
    reg.reviewed_by = admin_user.id

    db.session.add(
        AuditLog(
            user_id=admin_user.id,
            action="info_requested",
            entity_type="product_registration",
            entity_id=reg.id,
            details={"message": notes},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    flash("Additional information requested.", "info")
    return redirect(url_for("admin.view_registration", reg_id=reg_id))


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------
@admin_bp.route("/tickets")
@admin_required
def list_tickets():
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    query = SupportTicket.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    tickets = query.order_by(SupportTicket.updated_at.desc()).all()
    return render_template(
        "admin_panel/tickets.html",
        tickets=tickets,
        status_filter=status_filter,
        priority_filter=priority_filter,
    )


@admin_bp.route("/tickets/<int:ticket_id>")
@admin_required
def view_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    return render_template("admin_panel/ticket_detail.html", ticket=ticket)


@admin_bp.route("/tickets/<int:ticket_id>/reply", methods=["POST"])
@admin_required
def reply_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    admin_user = get_current_user()

    body = request.form.get("body", "").strip()
    new_status = request.form.get("status", "")
    new_priority = request.form.get("priority", "")
    tags = request.form.get("admin_tags", "").strip()

    if body:
        message = TicketMessage(
            ticket_id=ticket.id,
            sender_id=admin_user.id,
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

    if new_status:
        ticket.status = new_status
    if new_priority:
        ticket.priority = new_priority
    if tags:
        ticket.admin_tags = tags

    db.session.commit()
    flash("Ticket updated.", "success")
    return redirect(url_for("admin.view_ticket", ticket_id=ticket_id))


@admin_bp.route("/tickets/<int:ticket_id>/status", methods=["POST"])
@admin_required
def update_ticket_status(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    new_status = request.form.get("status", "")
    if new_status in ("open", "in_progress", "resolved"):
        ticket.status = new_status
        db.session.commit()
        flash(f"Ticket status updated to {new_status}.", "success")
    return redirect(url_for("admin.view_ticket", ticket_id=ticket_id))


# ---------------------------------------------------------------------------
# Customer Management
# ---------------------------------------------------------------------------
@admin_bp.route("/customers")
@admin_required
def list_customers():
    search = request.args.get("search", "").strip()
    query = User.query.filter_by(role="customer")

    if search:
        query = query.filter(
            db.or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )

    customers = query.order_by(User.created_at.desc()).all()
    return render_template(
        "admin_panel/customers.html", customers=customers, search=search
    )


@admin_bp.route("/customers/<int:customer_id>")
@admin_required
def view_customer(customer_id):
    customer = User.query.filter_by(id=customer_id, role="customer").first_or_404()
    registrations = customer.registrations.order_by(
        ProductRegistration.created_at.desc()
    ).all()
    tickets = customer.tickets.order_by(SupportTicket.created_at.desc()).all()
    return render_template(
        "admin_panel/customer_detail.html",
        customer=customer,
        registrations=registrations,
        tickets=tickets,
    )


# ---------------------------------------------------------------------------
# Mattress Models
# ---------------------------------------------------------------------------
@admin_bp.route("/models", methods=["GET", "POST"])
@admin_required
def manage_models():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip() or None
        description = request.form.get("description", "").strip() or None
        warranty_months = request.form.get("warranty_months", type=int) or 120

        if not name:
            flash("Model name is required.", "danger")
        elif MattressModel.query.filter_by(name=name).first():
            flash("A model with this name already exists.", "danger")
        else:
            model = MattressModel(
                name=name,
                sku=sku,
                description=description,
                warranty_months=warranty_months,
            )
            db.session.add(model)
            db.session.commit()
            flash(f"Model '{name}' added.", "success")
            return redirect(url_for("admin.manage_models"))

    models = MattressModel.query.order_by(MattressModel.name).all()
    return render_template("admin_panel/models.html", models=models)


# ---------------------------------------------------------------------------
# Fraud Alerts
# ---------------------------------------------------------------------------
@admin_bp.route("/fraud-alerts")
@admin_required
def fraud_alerts():
    flagged = get_fraud_indicators()
    return render_template("admin_panel/fraud_alerts.html", flagged=flagged)


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
@admin_bp.route("/audit-log")
@admin_required
def audit_log():
    page = request.args.get("page", 1, type=int)
    logs = (
        AuditLog.query.order_by(AuditLog.created_at.desc())
        .limit(100)
        .offset((page - 1) * 100)
        .all()
    )
    return render_template("admin_panel/audit_log.html", logs=logs, page=page)


# ---------------------------------------------------------------------------
# Serve uploads for admin
# ---------------------------------------------------------------------------
@admin_bp.route("/uploads/<path:filename>")
@admin_required
def serve_upload(filename):
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    return send_from_directory(upload_folder, filename)
