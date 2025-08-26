import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from forms import LoginForm


auth_bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/admin")
def admin():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        expected = os.environ.get("ADMIN_PASSWORD", "admin123")
        if password == expected:
            session.clear()
            session["logged_in"] = True
            return redirect(url_for("groups.list_groups"))
        flash("Invalid password", "danger")
    return render_template("login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("auth.login"))
