"""The bot's only way to the system: the REST API, as the Telegram user (D10 — the bot never
touches the database). Every call carries the service token and the user's Telegram id, so
the API applies that user's own permissions."""

import time

import httpx


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail

    @property
    def not_linked(self) -> bool:
        return self.code == "not_linked"


def _error(response: httpx.Response) -> ApiError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if isinstance(body, dict):
        code = str(body.get("code") or "")
        detail = body.get("detail")
        if isinstance(detail, dict):  # {"detail": {"code": ..., "detail": ...}}
            code, detail = str(detail.get("code", code)), detail.get("detail")
        if detail is None:  # field errors: {"qty": ["..."]}
            detail = "; ".join(f"{k}: {' '.join(map(str, v)) if isinstance(v, list) else v}"
                               for k, v in body.items())
    else:
        code, detail = "", str(body)
    if response.status_code == 403 and not code:
        code = "permission_denied"
    return ApiError(response.status_code, code, str(detail or response.reason_phrase))


class ApiClient:
    ME_TTL = 60  # seconds the user's role is remembered

    def __init__(self, base_url: str, service_token: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", timeout=20,
                                         transport=transport)
        self._token = service_token
        self._me: dict[int, tuple[float, dict]] = {}

    async def close(self):
        await self._client.aclose()

    def _headers(self, telegram_id: int | None) -> dict:
        headers = {"Authorization": f"Bot {self._token}", "X-Client": "bot"}
        if telegram_id is not None:
            headers["X-Telegram-User"] = str(telegram_id)
        return headers

    async def call(self, method: str, path: str, telegram_id: int | None, *, json=None,
                   params=None, raw: bool = False):
        response = await self._client.request(method, path.lstrip("/"), json=json,
                                              params=params, headers=self._headers(telegram_id))
        if response.status_code >= 400:
            raise _error(response)
        if raw:
            return response
        return response.json() if response.content else None

    # ------------------------------------------------------------ account
    async def link(self, code: str, telegram_id: int) -> dict:
        self._me.pop(telegram_id, None)
        return await self.call("POST", "auth/telegram/link/", None,
                               json={"code": code, "telegram_id": telegram_id})

    async def me(self, telegram_id: int) -> dict:
        cached = self._me.get(telegram_id)
        if cached and time.monotonic() - cached[0] < self.ME_TTL:
            return cached[1]
        data = await self.call("GET", "auth/me/", telegram_id)
        self._me[telegram_id] = (time.monotonic(), data)
        return data

    # ------------------------------------------------------------ lookups
    async def search(self, telegram_id: int, q: str) -> dict:
        return await self.call("GET", "search/", telegram_id, params={"q": q})

    async def stock_requests(self, telegram_id: int, status: str) -> list[dict]:
        data = await self.call("GET", "stock-requests/", telegram_id,
                               params={"status": status, "ordering": "created_at"})
        return data["results"]

    async def stock_request(self, telegram_id: int, request_id: int) -> dict:
        return await self.call("GET", f"stock-requests/{request_id}/", telegram_id)

    async def transfers_in_transit(self, telegram_id: int, to_location: int) -> list[dict]:
        data = await self.call("GET", "transfers/", telegram_id,
                               params={"status": "in_transit", "to_location": to_location})
        return data["results"]

    async def unverified_payments(self, telegram_id: int) -> list[dict]:
        data = await self.call("GET", "payments/", telegram_id,
                               params={"status": "unverified", "ordering": "paid_at"})
        return data["results"]

    async def my_orders(self, telegram_id: int) -> list[dict]:
        data = await self.call("GET", "orders/", telegram_id, params={"ordering": "-created_at"})
        return data["results"][:10]

    async def balances(self, telegram_id: int, location: int) -> list[dict]:
        data = await self.call("GET", "stock/", telegram_id, params={"location": location})
        return data["results"]

    async def low_stock(self, telegram_id: int) -> list[dict]:
        data = await self.call("GET", "stock/summary/", telegram_id, params={"low": "true"})
        return data["results"]

    async def movements(self, telegram_id: int, location: int | None) -> list[dict]:
        params = {"ordering": "-occurred_at"}
        if location:
            params["location"] = location
        data = await self.call("GET", "stock/movements/", telegram_id, params=params)
        return data["results"][:15]

    async def report(self, telegram_id: int, name: str, period: str = "day") -> dict:
        return await self.call("GET", f"reports/{name}/", telegram_id, params={"period": period})

    async def report_xlsx(self, telegram_id: int, name: str, period: str) -> tuple[str, bytes]:
        response = await self.call("GET", f"reports/{name}/", telegram_id, raw=True,
                                   params={"period": period, "format": "xlsx"})
        disposition = response.headers.get("Content-Disposition", "")
        filename = disposition.split("filename=")[-1].strip('"') or f"{name}.xlsx"
        return filename, response.content

    # ------------------------------------------------------------ actions
    async def acknowledge(self, telegram_id: int, request_id: int) -> dict:
        return await self.call("POST", f"stock-requests/{request_id}/acknowledge/", telegram_id)

    async def reject_request(self, telegram_id: int, request_id: int, reason: str) -> dict:
        return await self.call("POST", f"stock-requests/{request_id}/reject/", telegram_id,
                               json={"reason": reason})

    async def release(self, telegram_id: int, request_id: int, payload: dict) -> dict:
        return await self.call("POST", f"stock-requests/{request_id}/release/", telegram_id,
                               json=payload)

    async def create_request(self, telegram_id: int, product_id: int, qty: int,
                             reference: str = "") -> dict:
        return await self.call("POST", "stock-requests/", telegram_id,
                               json={"lines": [{"product": product_id, "qty": qty}],
                                     "reference": reference})

    async def receive_transfer(self, telegram_id: int, transfer_id: int) -> dict:
        return await self.call("POST", f"transfers/{transfer_id}/receive/", telegram_id,
                               json={})

    async def verify_payment(self, telegram_id: int, payment_id: int) -> dict:
        return await self.call("POST", f"payments/{payment_id}/verify/", telegram_id)

    async def reject_payment(self, telegram_id: int, payment_id: int, reason: str) -> dict:
        return await self.call("POST", f"payments/{payment_id}/reject/", telegram_id,
                               json={"reason": reason})
