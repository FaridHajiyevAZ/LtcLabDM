import os
import pytest

os.environ["FLASK_ENV"] = "testing"

from app import create_app
from models import db as _db, User, MattressModel


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    app = create_app("testing")
    return app


@pytest.fixture(autouse=True)
def db(app):
    """Create fresh database tables for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def sample_customer(db):
    """Create a verified customer user."""
    user = User(
        full_name="Test Customer",
        email="customer@test.com",
        phone="+1234567890",
        role="customer",
        is_verified=True,
    )
    user.set_password("password1")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_admin(db):
    """Create an admin user."""
    admin = User(
        full_name="Test Admin",
        email="admin@test.com",
        role="admin",
        is_verified=True,
    )
    admin.set_password("adminpass1")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def sample_model(db):
    """Create a sample mattress model."""
    model = MattressModel(
        name="Test Mattress Premium",
        sku="TM-PRM-001",
        warranty_months=120,
        is_active=True,
    )
    db.session.add(model)
    db.session.commit()
    return model


@pytest.fixture
def logged_in_customer(client, sample_customer):
    """Log in as customer and return client."""
    with client.session_transaction() as sess:
        sess["user_id"] = sample_customer.id
        sess["role"] = "customer"
        sess["full_name"] = sample_customer.full_name
    return client


@pytest.fixture
def logged_in_admin(client, sample_admin):
    """Log in as admin and return client."""
    with client.session_transaction() as sess:
        sess["user_id"] = sample_admin.id
        sess["role"] = "admin"
        sess["full_name"] = sample_admin.full_name
    return client
