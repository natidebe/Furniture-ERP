"""The bot's step-by-step logic as plain data and functions, so it can be tested without
Telegram. Handlers keep a flow's state (as a dict) in aiogram's FSM storage."""

from dataclasses import asdict, dataclass, field


def parse_callback(data: str) -> tuple[str, str, int]:
    """"req:rel:12" → ("req", "rel", 12). Raises ValueError on anything else."""
    kind, action, raw_id = data.split(":")
    return kind, action, int(raw_id)


def parse_qty(text: str, maximum: int) -> int:
    """A typed quantity between 0 and `maximum` (0 = skip this line)."""
    text = (text or "").strip()
    if not text.isdigit():
        raise ValueError("Type a whole number.")
    qty = int(text)
    if qty > maximum:
        raise ValueError(f"At most {maximum}.")
    return qty


@dataclass
class ReleaseDraft:
    """The storekeeper's release of one request (BUILD_PHASES.md 4.2):
    1) a quantity for each open line, 2) the destination, 3) confirm."""

    request_id: int
    number: str
    has_customer: bool
    lines: list[dict]                 # [{"id", "code", "name", "remaining"}] — open lines
    chosen: dict = field(default_factory=dict)  # str(line_id) → qty
    index: int = 0
    destination: str | None = None

    @classmethod
    def from_request(cls, request: dict) -> "ReleaseDraft":
        if request["status"] not in ("acknowledged", "partially_released"):
            raise ValueError(f"{request['number']} is {request['status'].replace('_', ' ')}; "
                             "acknowledge it first." if request["status"] == "pending"
                             else f"{request['number']} is not open for release.")
        lines = [{"id": ln["id"], "code": ln["product_code"], "name": ln["product_name"],
                  "remaining": ln["qty_remaining"]}
                 for ln in request["lines"] if ln["qty_remaining"] > 0]
        if not lines:
            raise ValueError(f"Nothing left to release on {request['number']}.")
        return cls(request_id=request["id"], number=request["number"],
                   has_customer=request.get("customer") is not None, lines=lines)

    @classmethod
    def load(cls, data: dict) -> "ReleaseDraft":
        return cls(**data)

    def dump(self) -> dict:
        return asdict(self)

    @property
    def current(self) -> dict | None:
        return self.lines[self.index] if self.index < len(self.lines) else None

    def set_qty(self, qty: int) -> None:
        line = self.current
        if line is None:
            raise ValueError("All lines are done.")
        if not 0 <= qty <= line["remaining"]:
            raise ValueError(f"{line['code']}: between 0 and {line['remaining']}.")
        self.chosen[str(line["id"])] = qty
        self.index += 1

    @property
    def lines_done(self) -> bool:
        return self.current is None

    def set_destination(self, destination: str) -> None:
        if destination not in ("branch", "customer_pickup"):
            raise ValueError("Choose a destination.")
        if destination == "customer_pickup" and not self.has_customer:
            raise ValueError("This request names no customer, so it can only go to the branch.")
        self.destination = destination

    def payload(self) -> dict:
        lines = [{"line_id": int(line_id), "qty": qty}
                 for line_id, qty in self.chosen.items() if qty > 0]
        if not lines:
            raise ValueError("Nothing chosen to release.")
        if self.destination is None:
            raise ValueError("Choose a destination.")
        return {"destination_type": self.destination, "lines": lines}

    def summary(self) -> str:
        by_id = {str(line["id"]): line for line in self.lines}
        items = [f"• {qty} × {by_id[line_id]['code']} {by_id[line_id]['name']}"
                 for line_id, qty in self.chosen.items() if qty > 0]
        where = {"branch": "to the branch", "customer_pickup": "to the customer (pickup)"}
        return (f"Release {self.number} {where.get(self.destination, '')}:\n"
                + ("\n".join(items) or "(nothing)"))
