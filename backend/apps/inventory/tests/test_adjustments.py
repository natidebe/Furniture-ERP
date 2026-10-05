import pytest

from apps.accounts.models import ERPPermission
from apps.accounts.services import set_erp_permissions
from apps.core.exceptions import BusinessRuleError
from apps.inventory import services
from apps.inventory.models import AdjustmentStatus, MovementType


@pytest.mark.django_db
def test_storekeeper_proposes_accountant_approves(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 10)

    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=-2,
                                             reason="damage", user=staff.store,
                                             note="Broken legs")
    assert balance(product, loc.PAW) == (10, 0)  # nothing moves until approved

    services.approve_adjustment(adjustment=adjustment, user=staff.accountant)

    adjustment.refresh_from_db()
    assert adjustment.status == AdjustmentStatus.APPROVED
    assert adjustment.decided_by == staff.accountant
    assert adjustment.movement.type == MovementType.ADJUSTMENT
    assert adjustment.movement.from_location == loc.PAW
    assert balance(product, loc.PAW) == (8, 0)


@pytest.mark.django_db
def test_positive_adjustment_adds_stock(staff, loc, product, balance):
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=3,
                                             reason="found", user=staff.store)
    services.approve_adjustment(adjustment=adjustment, user=staff.accountant)

    assert balance(product, loc.PAW) == (3, 0)


@pytest.mark.django_db
def test_salesperson_and_other_location_cannot_propose(staff, loc, product):
    with pytest.raises(BusinessRuleError):
        services.propose_adjustment(location=loc.PIA, product=product, qty_delta=1,
                                    reason="found", user=staff.sales)
    with pytest.raises(BusinessRuleError) as exc:
        services.propose_adjustment(location=loc.PIA, product=product, qty_delta=1,
                                    reason="found", user=staff.store)
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
def test_zero_change_is_refused(staff, loc, product):
    with pytest.raises(BusinessRuleError) as exc:
        services.propose_adjustment(location=loc.PAW, product=product, qty_delta=0,
                                    reason="count", user=staff.store)
    assert exc.value.code == "invalid_qty"


@pytest.mark.django_db
def test_accountant_cannot_approve_own_adjustment_but_admin_can(staff, loc, product):
    own = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                      reason="found", user=staff.accountant)
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_adjustment(adjustment=own, user=staff.accountant)
    assert exc.value.code == "own_adjustment"

    admins = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                         reason="found", user=staff.admin)
    services.approve_adjustment(adjustment=admins, user=staff.admin)


@pytest.mark.django_db
def test_approval_needs_the_permission(staff, loc, product):
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                             reason="found", user=staff.store)
    set_erp_permissions(staff.accountant, [ERPPermission.VERIFY_PAYMENTS])

    with pytest.raises(BusinessRuleError) as exc:
        services.approve_adjustment(adjustment=adjustment, user=staff.accountant)
    assert exc.value.code == "permission_denied"


@pytest.mark.django_db
def test_decided_adjustment_cannot_be_decided_again(staff, loc, product):
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                             reason="found", user=staff.store)
    services.approve_adjustment(adjustment=adjustment, user=staff.accountant)

    with pytest.raises(BusinessRuleError) as exc:
        services.reject_adjustment(adjustment=adjustment, user=staff.admin, note="no")
    assert exc.value.code == "invalid_state"


@pytest.mark.django_db
def test_reject_needs_a_note_and_moves_nothing(staff, loc, product, balance):
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=5,
                                             reason="found", user=staff.store)
    with pytest.raises(BusinessRuleError):
        services.reject_adjustment(adjustment=adjustment, user=staff.accountant, note="")

    services.reject_adjustment(adjustment=adjustment, user=staff.accountant, note="Recount")

    adjustment.refresh_from_db()
    assert adjustment.status == AdjustmentStatus.REJECTED
    assert balance(product, loc.PAW) == (0, 0)


@pytest.mark.django_db
def test_removal_beyond_free_stock_fails_at_approval(staff, loc, product, stock):
    stock(product, loc.PAW, 5)
    services.reserve(product=product, location=loc.PAW, qty=4)
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=-3,
                                             reason="loss", user=staff.store)

    with pytest.raises(BusinessRuleError) as exc:
        services.approve_adjustment(adjustment=adjustment, user=staff.accountant)
    assert exc.value.code == "insufficient_stock"


@pytest.mark.django_db
def test_api_storekeeper_cannot_approve(client_for, loc, product, make_user):
    store = make_user(role="storekeeper", home_location=loc.PAW)
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                             reason="found", user=store)
    client, _ = client_for("storekeeper", home_location=loc.PAW)

    response = client.post(f"/api/v1/adjustments/{adjustment.pk}/approve/", {}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_api_accountant_without_permission_gets_403(client_for, loc, product, make_user):
    store = make_user(role="storekeeper", home_location=loc.PAW)
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=1,
                                             reason="found", user=store)
    client, accountant = client_for("accountant")
    set_erp_permissions(accountant, [])

    response = client.post(f"/api/v1/adjustments/{adjustment.pk}/approve/", {}, format="json")

    assert response.status_code == 403
