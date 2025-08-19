from flask import Blueprint, render_template, redirect, url_for, flash
from flask import request
from models import db, Group
from forms import GroupForm
from auth import login_required


groups_bp = Blueprint("groups", __name__)


@groups_bp.route("/")
@login_required
def index():
    return redirect(url_for("groups.list_groups"))


@groups_bp.route("/groups", methods=["GET", "POST"])
@login_required
def list_groups():
    form = GroupForm()
    if form.validate_on_submit():
        group = Group(
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
        )
        db.session.add(group)
        db.session.commit()
        flash("Group created")
        return redirect(url_for("groups.list_groups"))
    groups = Group.query.all()
    return render_template("groups.html", form=form, groups=groups)


@groups_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id):
    group = Group.query.get_or_404(group_id)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        group.name = form.name.data
        group.start_date = form.start_date.data
        group.end_date = form.end_date.data
        db.session.commit()
        flash("Group updated")
        return redirect(url_for("groups.list_groups"))
    return render_template("group_edit.html", form=form, group=group)


@groups_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    flash("Group deleted")
    return redirect(url_for("groups.list_groups"))
