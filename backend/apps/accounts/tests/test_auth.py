import pytest

from tests.factories import DEFAULT_PASSWORD

TOKEN_URL = "/api/v1/auth/token/"


def _login(api_client, username, password):
    return api_client.post(TOKEN_URL, {"username": username, "password": password},
                           format="json", REMOTE_ADDR="10.0.0.5")


@pytest.mark.django_db
def test_login_returns_jwt_pair(api_client, make_user):
    user = make_user()

    response = _login(api_client, user.username, DEFAULT_PASSWORD)

    assert response.status_code == 200
    assert {"access", "refresh"} <= response.data.keys()


@pytest.mark.django_db
def test_lockout_after_five_bad_passwords(api_client, make_user):
    user = make_user()

    for _ in range(5):
        assert _login(api_client, user.username, "wrong").status_code != 200

    # Locked out: even the right password is refused now.
    assert _login(api_client, user.username, DEFAULT_PASSWORD).status_code != 200


@pytest.mark.django_db
def test_me_returns_profile_and_permissions(client_for):
    client, user = client_for("accountant")

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.data["id"] == user.id
    assert response.data["name"] == user.full_name
    assert response.data["role"] == "accountant"
    assert isinstance(response.data["permissions"], list)


@pytest.mark.django_db
def test_me_requires_login(api_client):
    assert api_client.get("/api/v1/auth/me/").status_code == 401
