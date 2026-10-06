from django.template.loader import render_to_string

from apps.core.ethiopian import format_both
from apps.payments import selectors as money


def delivery_note_context(note) -> dict:
    order = note.order
    lines = []
    for line in note.lines.select_related("order_line", "product"):
        unit = line.order_line.line_total / line.order_line.qty  # discount spread evenly
        lines.append({"code": line.product.code, "name": line.product.name, "qty": line.qty,
                      "unit_price": unit, "total": unit * line.qty})
    paid = money.order_paid(order)
    return {
        "note": note, "order": order, "customer": order.customer, "lines": lines,
        "issued": format_both(note.issued_at, with_time=True),
        "order_total": order.total_amount, "paid": paid,
        "remaining": order.total_amount - paid,
    }


def delivery_note_html(note) -> str:
    return render_to_string("sales/delivery_note.html", delivery_note_context(note))


def delivery_note_pdf(note) -> bytes:
    """Render with WeasyPrint (needs Pango; installed in the Docker image)."""
    from weasyprint import HTML

    return HTML(string=delivery_note_html(note)).write_pdf()
