from flask_wtf import FlaskForm
from wtforms import StringField, DateField, PasswordField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired()])


class GroupForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date")


class StudentForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired()])


class ClassDayForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()])
