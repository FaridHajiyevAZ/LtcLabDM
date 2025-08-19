from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    students = db.relationship("Student", backref="group", cascade="all, delete-orphan")
    class_days = db.relationship(
        "ClassDay", backref="group", cascade="all, delete-orphan"
    )


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    attendances = db.relationship(
        "Attendance", backref="student", cascade="all, delete-orphan"
    )


class ClassDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    attendances = db.relationship(
        "Attendance", backref="class_day", cascade="all, delete-orphan"
    )
    __table_args__ = (db.UniqueConstraint("group_id", "date", name="uix_group_date"),)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    class_day_id = db.Column(db.Integer, db.ForeignKey("class_day.id"), nullable=False)
    present = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("student_id", "class_day_id", name="uix_student_class"),
    )
