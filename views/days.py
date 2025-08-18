from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db, Group, ClassDay, Attendance
from forms import ClassDayForm
from auth import login_required


days_bp = Blueprint("days", __name__)


@days_bp.route("/groups/<int:group_id>/days", methods=["GET", "POST"])
@login_required
def manage_days(group_id):
    group = Group.query.get_or_404(group_id)
    form = ClassDayForm()
    if form.validate_on_submit():
        exists = ClassDay.query.filter_by(
            group_id=group_id, date=form.date.data
        ).first()
        if exists:
            flash("Class day already exists", "warning")
        else:
            day = ClassDay(group=group, date=form.date.data)
            db.session.add(day)
            db.session.commit()
            flash("Class day added")
        return redirect(url_for("days.manage_days", group_id=group_id))
    days = ClassDay.query.filter_by(group_id=group_id).order_by(ClassDay.date).all()
    return render_template("days.html", group=group, form=form, days=days)


@days_bp.route("/days/<int:day_id>/delete", methods=["POST"])
@login_required
def delete_day(day_id):
    day = ClassDay.query.get_or_404(day_id)
    if day.attendances:
        flash("Cannot delete day with attendance", "danger")
        return redirect(url_for("days.manage_days", group_id=day.group_id))
    group_id = day.group_id
    db.session.delete(day)
    db.session.commit()
    flash("Class day deleted")
    return redirect(url_for("days.manage_days", group_id=group_id))
