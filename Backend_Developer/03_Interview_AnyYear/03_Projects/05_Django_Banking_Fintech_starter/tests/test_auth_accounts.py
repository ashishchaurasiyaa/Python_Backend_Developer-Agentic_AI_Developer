import pytest

from tests.helpers import auth_headers_for

pytestmark = pytest.mark.django_db


def test_signup_creates_user(api_client, unique_username):
    resp = api_client.post("/auth/signup", {
        "username": unique_username, "email": f"{unique_username}@example.com", "password": "CorrectHorse9!",
    }, format="json")
    assert resp.status_code == 201
    assert resp.json()["username"] == unique_username


def test_login_returns_jwt(api_client, unique_username):
    api_client.post("/auth/signup", {"username": unique_username, "password": "CorrectHorse9!"}, format="json")
    resp = api_client.post("/auth/login", {"username": unique_username, "password": "CorrectHorse9!"}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json() and "refresh" in resp.json()


def test_login_wrong_password_rejected(api_client, unique_username):
    api_client.post("/auth/signup", {"username": unique_username, "password": "CorrectHorse9!"}, format="json")
    resp = api_client.post("/auth/login", {"username": unique_username, "password": "wrong"}, format="json")
    assert resp.status_code == 401


def test_open_account_requires_auth(api_client):
    resp = api_client.post("/accounts", {"account_type": "savings"}, format="json")
    assert resp.status_code == 401


def test_open_account_succeeds(api_client, unique_username):
    api_client.post("/auth/signup", {"username": unique_username, "password": "CorrectHorse9!"}, format="json")
    headers = auth_headers_for(api_client, unique_username, "CorrectHorse9!")
    resp = api_client.post("/accounts", {"account_type": "savings"}, format="json", **headers)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["account_number"]) == 14
    assert body["balance"]["current_balance"] == "0.0000"


def test_account_list_only_shows_own_accounts(api_client, unique_username):
    api_client.post("/auth/signup", {"username": unique_username, "password": "CorrectHorse9!"}, format="json")
    other_username = f"{unique_username}_other"
    api_client.post("/auth/signup", {"username": other_username, "password": "CorrectHorse9!"}, format="json")

    headers = auth_headers_for(api_client, unique_username, "CorrectHorse9!")
    api_client.post("/accounts", {"account_type": "savings"}, format="json", **headers)

    other_headers = auth_headers_for(api_client, other_username, "CorrectHorse9!")
    resp = api_client.get("/accounts", **other_headers)
    assert resp.status_code == 200
    assert resp.json() == []
