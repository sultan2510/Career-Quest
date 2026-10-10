"""Both documented launch paths must expose the real application."""
from fastapi.testclient import TestClient
from api import app, create_app
from backend.main import app as careerquest_app


def test_legacy_launch_path_uses_integrated_backend():
    assert app is careerquest_app
    assert create_app() is careerquest_app


def test_real_routes_are_registered_and_placeholder_routes_are_absent():
    paths = {route.path for route in app.routes}
    assert {'/auth/signup', '/auth/login', '/auth/me', '/progress', '/rag/ask'} <= paths
    assert '/user/profile' not in paths


def test_health_and_openapi_without_external_services():
    client = TestClient(app)
    assert client.get('/health').json() == {'ok': True}
    schema = client.get('/openapi.json').json()
    assert '/rag/ask' in schema['paths']
    assert '/progress' in schema['paths']
