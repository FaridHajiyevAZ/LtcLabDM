import os
from datetime import date
from flask import Flask
from flask_wtf import CSRFProtect
from models import db, Group


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        os.makedirs(app.instance_path, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
            app.instance_path, "app.db"
        )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    CSRFProtect(app)

    from auth import auth_bp
    from views.groups import groups_bp
    from views.students import students_bp
    from views.days import days_bp
    from views.attendance import attendance_bp
    from views.scores import scores_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(days_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(scores_bp)

    @app.cli.command("seed")
    def seed():
        g = Group(name="Demo Group", start_date=date.today(), end_date=date.today())
        db.session.add(g)
        db.session.commit()

    with app.app_context():
        db.create_all()

    return app


app = create_app()
