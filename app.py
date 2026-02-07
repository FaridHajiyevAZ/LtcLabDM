import os

from flask import Flask
from flask_wtf import CSRFProtect

from models import db


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    # Load config
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    from config import config_map

    app.config.from_object(config_map.get(config_name, config_map["development"]))

    # Ensure instance folder and upload folder exist
    os.makedirs(app.instance_path, exist_ok=True)
    upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(app.root_path, upload_folder)
        app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(upload_folder, exist_ok=True)

    # Handle SQLite path for development
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if db_uri and db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:////"):
        relative = db_uri.replace("sqlite:///", "")
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
            app.instance_path, os.path.basename(relative)
        )

    # Initialize extensions
    db.init_app(app)
    CSRFProtect(app)

    # Register blueprints
    from auth import auth_bp
    from views.customer import customer_bp
    from views.admin_panel import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)

    # CLI commands
    @app.cli.command("seed")
    def seed():
        """Seed the database with initial data."""
        from models import User, MattressModel

        admin = User.query.filter_by(email="admin@warranty.local").first()
        if not admin:
            admin = User(
                full_name="System Admin",
                email="admin@warranty.local",
                role="admin",
                is_verified=True,
            )
            admin.set_password(os.environ.get("ADMIN_PASSWORD", "admin123"))
            db.session.add(admin)

        sample_models = [
            ("CloudRest Premium", "CR-PRM-001", 120),
            ("CloudRest Standard", "CR-STD-001", 60),
            ("DreamSoft Orthopedic", "DS-ORT-001", 120),
            ("DreamSoft Memory Foam", "DS-MF-001", 84),
            ("NatureSleep Latex", "NS-LTX-001", 120),
        ]
        for name, sku, months in sample_models:
            if not MattressModel.query.filter_by(name=name).first():
                db.session.add(
                    MattressModel(name=name, sku=sku, warranty_months=months)
                )

        db.session.commit()
        print("Database seeded successfully.")

    @app.cli.command("create-admin")
    def create_admin_cmd():
        """Create an admin user interactively."""
        import getpass

        email = input("Admin email: ").strip()
        name = input("Full name: ").strip()
        password = getpass.getpass("Password: ")

        from models import User

        if User.query.filter_by(email=email).first():
            print(f"User with email {email} already exists.")
            return

        admin = User(
            full_name=name,
            email=email,
            role="admin",
            is_verified=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user {email} created.")

    with app.app_context():
        db.create_all()

    return app


app = create_app()
