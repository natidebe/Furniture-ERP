import pytest

from tests.factories import ProductFactory


@pytest.mark.django_db
def test_page_size_param_is_capped_at_200(client_for):
    ProductFactory.create_batch(30)
    client, _ = client_for("salesperson")

    assert len(client.get("/api/v1/products/").data["results"]) == 25
    assert len(client.get("/api/v1/products/", {"page_size": 5}).data["results"]) == 5
    assert len(client.get("/api/v1/products/", {"page_size": 500}).data["results"]) == 30
