from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db, Group, Student, ClassDay, Attendance
from auth import login_required


attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/groups/<int:group_id>/attendance", methods=["GET", "POST"])
@login_required
def take_attendance(group_id):
    date_str = request.args.get("date")
    group = Group.query.get_or_404(group_id)
    if not date_str:
        flash("Select a date", "warning")
        return redirect(url_for("days.manage_days", group_id=group_id))
    try:
        day_date = date.fromisoformat(date_str)
    except ValueError:
        flash("Invalid date", "danger")
        return redirect(url_for("days.manage_days", group_id=group_id))
    day = ClassDay.query.filter_by(group_id=group_id, date=day_date).first()
    if not day:
        flash("Class day does not exist", "warning")
        return redirect(url_for("days.manage_days", group_id=group_id))

    students = (
        Student.query.filter_by(group_id=group_id).order_by(Student.full_name).all()
    )

    if request.method == "POST":
        for student in students:
            present = request.form.get(str(student.id)) == "on"
            attendance = Attendance.query.filter_by(
                student_id=student.id, class_day_id=day.id
            ).first()
            if not attendance:
                attendance = Attendance(student_id=student.id, class_day_id=day.id)
                db.session.add(attendance)
            attendance.present = present
        db.session.commit()
        flash("Attendance saved")
        return redirect(
            url_for("attendance.take_attendance", group_id=group_id, date=date_str)
        )

    attendance_map = {
        a.student_id: a.present
        for a in Attendance.query.filter_by(class_day_id=day.id).all()
    }
    return render_template(
        "attendance.html",
        group=group,
        day=day,
        students=students,
        attendance=attendance_map,
    )
