import os
import secrets
from functools import wraps
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
)

from models import db, User, OTPCode, AuditLog

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def login_required(view):
    """Require any authenticated user."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    """Require an authenticated customer."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "customer":
            flash("Access denied.", "danger")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Require an authenticated admin."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.admin_login"))
        if session.get("role") != "admin":
            flash("Access denied.", "danger")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def get_current_user():
    """Return the currently logged-in User or None."""
    user_id = session.get("user_id")
    if user_id:
        return db.session.get(User, user_id)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_email(email):
    if email:
        return email.strip().lower()
    return None


def _normalize_phone(phone):
    if phone:
        return "".join(c for c in phone.strip() if c.isdigit() or c == "+")
    return None


def _validate_password(password):
    """Return error message or None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isalpha() for c in password):
        return "Password must contain at least one letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit."
    return None


def _generate_otp(user, purpose):
    """Generate a 6-digit OTP code and store it."""
    expiry = current_app.config.get("OTP_EXPIRY_SECONDS", 600)
    code = f"{secrets.randbelow(1000000):06d}"
    otp = OTPCode(
        user_id=user.id,
        code=code,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expiry),
    )
    db.session.add(otp)
    db.session.commit()
    return code


def _log_audit(action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        user_id=session.get("user_id"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()


# ---------------------------------------------------------------------------
# Customer Registration
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = _normalize_email(request.form.get("email"))
        phone = _normalize_phone(request.form.get("phone"))
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        consent = request.form.get("consent")

        # Validation
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email and not phone:
            errors.append("Email or phone number is required.")
        if password != password_confirm:
            errors.append("Passwords do not match.")
        pw_error = _validate_password(password)
        if pw_error:
            errors.append(pw_error)
        if not consent:
            errors.append("You must accept the terms and conditions.")

        # Check uniqueness
        if email and User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        if phone and User.query.filter_by(phone=phone).first():
            errors.append("An account with this phone number already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html")

        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role="customer",
            consent_accepted_at=datetime.now(timezone.utc),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Generate verification OTP
        if email:
            otp_code = _generate_otp(user, "email_verify")
            # In production: send email with otp_code
            current_app.logger.info(
                f"Verification OTP for {email}: {otp_code}"
            )

        _log_audit("user_registered", "user", user.id)
        flash(
            "Account created. Please check your email for verification code.",
            "success",
        )
        return redirect(url_for("auth.verify_email", user_id=user.public_id))

    return render_template("auth/register.html")


# ---------------------------------------------------------------------------
# Email Verification
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/verify-email", methods=["GET", "POST"])
def verify_email():
    user_pid = request.args.get("user_id") or request.form.get("user_id")
    user = User.query.filter_by(public_id=user_pid).first() if user_pid else None

    if not user:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("auth.register"))

    if user.is_verified:
        flash("Account already verified. Please log in.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        otp = (
            OTPCode.query.filter_by(
                user_id=user.id, purpose="email_verify", is_used=False
            )
            .order_by(OTPCode.created_at.desc())
            .first()
        )

        if not otp or not otp.is_valid:
            flash("Invalid or expired code. Please request a new one.", "danger")
            return render_template("auth/verify_email.html", user_id=user_pid)

        otp.attempts += 1
        max_attempts = current_app.config.get("OTP_MAX_ATTEMPTS", 5)
        if otp.attempts > max_attempts:
            flash("Too many attempts. Please request a new code.", "danger")
            db.session.commit()
            return render_template("auth/verify_email.html", user_id=user_pid)

        if otp.code != code:
            flash("Incorrect code.", "danger")
            db.session.commit()
            return render_template("auth/verify_email.html", user_id=user_pid)

        otp.is_used = True
        user.is_verified = True
        db.session.commit()
        _log_audit("email_verified", "user", user.id)
        flash("Email verified successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/verify_email.html", user_id=user_pid)


# ---------------------------------------------------------------------------
# Customer Login
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = None
        email = _normalize_email(identifier)
        phone = _normalize_phone(identifier)

        if email and "@" in identifier:
            user = User.query.filter_by(email=email).first()
        elif phone:
            user = User.query.filter_by(phone=phone).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            _log_audit("login_failed", details={"identifier": identifier})
            return render_template("auth/login.html")

        if not user.is_active:
            flash("Account is deactivated. Contact support.", "danger")
            return render_template("auth/login.html")

        if not user.is_verified:
            flash("Please verify your email before logging in.", "warning")
            return redirect(
                url_for("auth.verify_email", user_id=user.public_id)
            )

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["full_name"] = user.full_name
        session.permanent = True
        _log_audit("login_success", "user", user.id)

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/login.html")


# ---------------------------------------------------------------------------
# Admin Login (separate route for clarity)
# ---------------------------------------------------------------------------
@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("user_id") and session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        email = _normalize_email(identifier)
        user = User.query.filter_by(email=email, role="admin").first()

        if not user or not user.check_password(password):
            flash("Invalid admin credentials.", "danger")
            return render_template("auth/admin_login.html")

        session.clear()
        session["user_id"] = user.id
        session["role"] = "admin"
        session["full_name"] = user.full_name
        session.permanent = True
        _log_audit("admin_login_success", "user", user.id)
        return redirect(url_for("admin.dashboard"))

    return render_template("auth/admin_login.html")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/logout", methods=["POST"])
@login_required
def logout():
    _log_audit("logout", "user", session.get("user_id"))
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Forgot Password
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        email = _normalize_email(identifier)
        user = User.query.filter_by(email=email).first() if email else None

        # Always show success to prevent user enumeration
        flash(
            "If an account exists with that email, a reset code has been sent.",
            "info",
        )
        if user:
            otp_code = _generate_otp(user, "password_reset")
            current_app.logger.info(
                f"Password reset OTP for {email}: {otp_code}"
            )
            return redirect(
                url_for("auth.reset_password", user_id=user.public_id)
            )
        return render_template("auth/forgot_password.html")

    return render_template("auth/forgot_password.html")


# ---------------------------------------------------------------------------
# Reset Password
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/reset-password", methods=["GET", "POST"])
def reset_password():
    user_pid = request.args.get("user_id") or request.form.get("user_id")
    user = User.query.filter_by(public_id=user_pid).first() if user_pid else None

    if not user:
        flash("Invalid reset link.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        otp = (
            OTPCode.query.filter_by(
                user_id=user.id, purpose="password_reset", is_used=False
            )
            .order_by(OTPCode.created_at.desc())
            .first()
        )

        if not otp or not otp.is_valid or otp.code != code:
            flash("Invalid or expired reset code.", "danger")
            return render_template("auth/reset_password.html", user_id=user_pid)

        pw_error = _validate_password(new_password)
        if pw_error:
            flash(pw_error, "danger")
            return render_template("auth/reset_password.html", user_id=user_pid)

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/reset_password.html", user_id=user_pid)

        otp.is_used = True
        user.set_password(new_password)
        db.session.commit()
        _log_audit("password_reset", "user", user.id)
        flash("Password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", user_id=user_pid)
