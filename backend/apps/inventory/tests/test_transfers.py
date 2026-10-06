import pytest

from apps.audit.models import AuditLog
from apps.core.exceptions import BusinessRuleError
from apps.inventory import services
from apps.inventory.models import StockMovement, TransferStatus


@pytest.fixture
def sent(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    return services.create_transfer(from_location=loc.PAW, to_location=loc.PIA,
                                    lines=[{"product": product, "qty": 6}], user=staff.accountant)


def _company_total(product):
    return sum(b.on_hand for b in product.balances.all())


@pytest.mark.django_db
def test_sent_transfer_sits_in_transit_and_total_is_unchanged(sent, loc, product, balance):
    assert sent.status == TransferStatus.IN_TRANSIT
    assert balance(product, loc.PAW) == (4, 0)
    assert balance(product, loc.TRANSIT) == (6, 0)
    assert balance(product, loc.PIA) == (0, 0)
    assert _company_total(product) == 10


@pytest.mark.django_db
def test_receiving_empties_transit_and_fills_destination(sent, staff, loc, product, balance):
    services.receive_transfer(transfer=sent, user=staff.sales)

    sent.refresh_from_db()
    assert sent.status == TransferStatus.RECEIVED
    assert sent.received_by == staff.sales
    assert not sent.has_discrepancy
    assert balance(product, loc.TRANSIT) == (0, 0)
    assert balance(product, loc.PIA) == (6, 0)
    assert _company_total(product) == 10
    numbers = set(StockMovement.objects.filter(reference_id=sent.number)
                  .values_list("transaction_number", flat=True))
    assert numbers == {sent.transaction_number}


@pytest.mark.django_db
def test_short_receipt_leaves_shortfall_in_transit_with_a_note(sent, staff, loc, product,
                                                               balance):
    line = sent.lines.get()

    services.receive_transfer(transfer=sent, user=staff.sales, received={line.pk: 4})

    sent.refresh_from_db()
    assert balance(product, loc.PIA) == (4, 0)
    assert balance(product, loc.TRANSIT) == (2, 0)
    assert "sent 6, received 4" in sent.discrepancy_note
    assert AuditLog.objects.filter(action="transfer_short_received").exists()


@pytest.mark.django_db
def test_only_destination_staff_receive(sent, staff):
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_transfer(transfer=sent, user=staff.den_sales)
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
def test_cannot_receive_twice_or_more_than_sent(sent, staff):
    line = sent.lines.get()
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_transfer(transfer=sent, user=staff.sales, received={line.pk: 7})
    assert exc.value.code == "invalid_qty"

    services.receive_transfer(transfer=sent, user=staff.sales)
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_transfer(transfer=sent, user=staff.sales)
    assert exc.value.code == "invalid_state"


@pytest.mark.django_db
def test_storekeeper_and_salesperson_cannot_send_manual_transfers(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    for user in (staff.store, staff.sales):
        with pytest.raises(BusinessRuleError) as exc:
            services.create_transfer(from_location=loc.PAW, to_location=loc.PIA,
                                     lines=[{"product": product, "qty": 1}], user=user)
        assert exc.value.code == "permission_denied"


@pytest.mark.django_db
def test_transfer_to_same_location_or_transit_is_refused(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    for target in (loc.PAW, loc.TRANSIT):
        with pytest.raises(BusinessRuleError):
            services.create_transfer(from_location=loc.PAW, to_location=target,
                                     lines=[{"product": product, "qty": 1}], user=staff.admin)


@pytest.mark.django_db
def test_api_receive(client_for, sent, loc, product, balance):
    client, _ = client_for("salesperson", home_location=loc.PIA)

    response = client.post(f"/api/v1/transfers/{sent.pk}/receive/", {}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "received"
    assert balance(product, loc.PIA) == (6, 0)


@pytest.mark.django_db
def test_api_storekeeper_cannot_create_manual_transfer(client_for, loc, product):
    client, _ = client_for("storekeeper", home_location=loc.PAW)

    response = client.post("/api/v1/transfers/", {
        "from_location": loc.PAW.pk, "to_location": loc.PIA.pk,
        "lines": [{"product": product.pk, "qty": 1}]}, format="json")

    assert response.status_code == 403
