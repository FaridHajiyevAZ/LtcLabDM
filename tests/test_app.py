from app import create_app


def test_app_creation():
    app = create_app("testing")
    assert app is not None
    assert app.config["TESTING"] is True


def test_app_has_blueprints():
    app = create_app("testing")
    assert "auth" in app.blueprints
    assert "customer" in app.blueprints
    assert "admin" in app.blueprints
