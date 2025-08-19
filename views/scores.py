import csv
from io import StringIO
from flask import Blueprint, render_template, Response
from models import db, Group, Student, Attendance
from auth import login_required


scores_bp = Blueprint("scores", __name__)


@scores_bp.route("/groups/<int:group_id>/scores")
@login_required
def show_scores(group_id):
    group = Group.query.get_or_404(group_id)
    data = []
    for student in group.students:
        total = Attendance.query.filter_by(student_id=student.id, present=True).count()
        data.append((student, total))
    return render_template("scores.html", group=group, data=data)


@scores_bp.route("/groups/<int:group_id>/scores.csv")
@login_required
def scores_csv(group_id):
    group = Group.query.get_or_404(group_id)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Student", "Points"])
    for student in group.students:
        total = Attendance.query.filter_by(student_id=student.id, present=True).count()
        writer.writerow([student.full_name, total])
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-disposition": f"attachment; filename=group-{group.id}-scores.csv"
        },
    )
