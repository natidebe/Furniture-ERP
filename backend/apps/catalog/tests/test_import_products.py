from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from openpyxl import Workbook

from apps.catalog.models import PriceHistory, Product


def _xlsx(tmp_path, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Code", "Name", "Category", "Unit", "Price"])
    for row in rows:
        ws.append(row)
    path = tmp_path / "products.xlsx"
    wb.save(path)
    return str(path)


@pytest.mark.django_db
def test_import_creates_products(tmp_path):
    path = _xlsx(tmp_path, [
        ["vc-001", "Visitor chair", "Visitor chairs", "pcs", 2500],
        ["DS-003", "Manager desk", "Desks", "Pieces", "18000.50"],
    ])

    call_command("import_products", path)

    assert Product.objects.get(code="VC-001").selling_price == Decimal("2500.00")
    assert Product.objects.get(code="DS-003").unit.symbol == "pcs"


@pytest.mark.django_db
def test_import_is_idempotent_and_records_price_changes(tmp_path):
    call_command("import_products",
                 _xlsx(tmp_path, [["VC-001", "Visitor chair", "Visitor chairs", "pcs", 2500]]))
    call_command("import_products",
                 _xlsx(tmp_path, [["VC-001", "Visitor chair", "Visitor chairs", "pcs", 2500]]))
    assert Product.objects.count() == 1
    assert not PriceHistory.objects.exists()

    call_command("import_products",
                 _xlsx(tmp_path, [["VC-001", "Visitor chair", "Visitor chairs", "pcs", 2600]]))

    assert Product.objects.get(code="VC-001").selling_price == Decimal("2600.00")
    assert PriceHistory.objects.get().reason == "import_products"


@pytest.mark.django_db
def test_dry_run_saves_nothing(tmp_path):
    call_command("import_products",
                 _xlsx(tmp_path, [["VC-001", "Visitor chair", "Visitor chairs", "pcs", 2500]]),
                 dry_run=True)

    assert not Product.objects.exists()


@pytest.mark.django_db
def test_any_bad_row_aborts_whole_import(tmp_path):
    path = _xlsx(tmp_path, [
        ["VC-001", "Visitor chair", "Visitor chairs", "pcs", 2500],
        ["VC-002", "Bad unit", "Visitor chairs", "boxes", 100],
        ["VC-003", "Bad price", "Visitor chairs", "pcs", 0],
    ])

    with pytest.raises(CommandError) as exc:
        call_command("import_products", path)

    assert "row 3" in str(exc.value) and "row 4" in str(exc.value)
    assert not Product.objects.exists()
