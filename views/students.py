from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db, Group, Student
from forms import StudentForm
from auth import login_required


students_bp = Blueprint("students", __name__)


@students_bp.route("/groups/<int:group_id>/students", methods=["GET", "POST"])
@login_required
def manage_students(group_id):
    group = Group.query.get_or_404(group_id)
    form = StudentForm()
    if form.validate_on_submit():
        student = Student(full_name=form.full_name.data, group=group)
        db.session.add(student)
        db.session.commit()
        flash("Student added")
        return redirect(url_for("students.manage_students", group_id=group_id))
    return render_template("students.html", group=group, form=form)


@students_bp.route("/students/<int:student_id>/edit", methods=["POST"])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    name = request.form.get("full_name")
    if name:
        student.full_name = name
        db.session.commit()
        flash("Student updated")
    return redirect(url_for("students.manage_students", group_id=student.group_id))


@students_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    group_id = student.group_id
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted")
    return redirect(url_for("students.manage_students", group_id=group_id))
