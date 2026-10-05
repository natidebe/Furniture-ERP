import pytest
from django.utils import timezone

from apps.accounts.models import TelegramLinkToken


@pytest.mark.django_db
def test_link_code_is_eight_characters_and_expires_in_ten_minutes(client_for):
    client, user = client_for("salesperson")

    response = client.post("/api/v1/auth/telegram/link-code/")

    assert response.status_code == 201
    token = TelegramLinkToken.objects.get(user=user)
    assert response.data["code"] == token.token
    assert len(token.token) == 8
    minutes_left = (token.expires_at - timezone.now()).total_seconds() / 60
    assert 9 < minutes_left <= 10
    assert token.is_valid


@pytest.mark.django_db
def test_new_code_replaces_unused_old_code(client_for):
    client, user = client_for("salesperson")

    first = client.post("/api/v1/auth/telegram/link-code/").data["code"]
    second = client.post("/api/v1/auth/telegram/link-code/").data["code"]

    assert first != second
    assert list(TelegramLinkToken.objects.filter(user=user).values_list("token", flat=True)) == [
        second]
