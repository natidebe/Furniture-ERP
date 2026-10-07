# Furniture ERP — Web UI Design Requirements

**For:** the designer and the frontend developer.
**Based on:** the client's requirements (`userequirements.md`), decisions D1–D16 in `BUILD_PHASES.md`, and the backend in `backend/` (Phases 1–4 built and tested).
**Last updated:** 7 Oct 2026

This document lists every page of the web app: who uses it, what it shows, what people can do there, the rules it must respect, and the API it calls. The backend for every page exists (section 8). Try any endpoint in Swagger at `/api/schema/swagger-ui/` with the demo users (see `backend/README.md`).

Places marked **[Q…]** depend on a client answer that is still open (section 9).

---

## 1. The business in one paragraph

An office-furniture importer with two shops — **Piassa** (the main branch, with a small **Underground** store) and **Denbel** — and the **Pawlos warehouse**, where most stock is kept. Walk-in customers usually pay at once; resellers and out-of-city shops (Jimma, Bahir Dar, Mekele…) often order by phone and buy on credit. Goods leave Pawlos only against a **stock request** from a branch. Money goes either to an **Organization** account (official receipt) or a **Personal** account, and the two must never be confused. The web app replaces the paper delivery pad and the accountant's Excel; Telegram carries alerts and quick actions.

## 2. Who uses it

| Role | Works at | Main jobs on the web |
| --- | --- | --- |
| **Salesperson** | Piassa or Denbel | Sell at the counter and by phone, check stock and prices, create customers, request stock from Pawlos, take payments into the accounts they're allowed, hand over goods, follow **their own** sales |
| **Storekeeper** | Pawlos | Work the request queue, release stock (the quantity actually taken out), receive imports, mark display/damaged pieces, propose stock corrections |
| **Accountant** | Office | All sales and stock history, record and verify payments, credit, approve corrections, reports and Excel |
| **Admin (owner)** | Anywhere | Everything, plus products and prices, users and permissions, locations, payment accounts, settings, audit log |

**Locations:** Piassa (PIA), Piassa Underground (PIA-UG), Denbel (DEN), Pawlos (PAW), and the system location **In Transit** for goods between locations. [Q4, Q18: Underground may be merged into Piassa.]

**What stays in Telegram (not the web):** request alerts with Acknowledge/Release buttons for the storekeeper, payment-to-verify alerts, low-stock alerts, the owner's daily/weekly/monthly/yearly reports. Everything the bot does is also possible on the web. **New sales and payments are entered only on the web (D10).**

---

## 3. Design rules for every page

### 3.1 Layout and devices

- **Desktop first** (counter and office PCs); every page must also work on a **tablet (1024 px)**. The storekeeper's pages (P-30–P-33, P-27, P-23) must work on a **phone (360 px)** — releases happen on the warehouse floor.
- **Left sidebar** with the role's menu (section 4), collapsible. **Top bar:** global search (always visible), today's date (Ethiopian first), the user's name, role and location, **My profile**, **Log out**.
- **Page header:** title · main action on the right (e.g. **New sale**) · filters · content.
- **Language:** English screen text; Ethiopian month names appear in Amharic script (e.g. መስከረም). Leave room for longer labels in case Amharic screens are added later.

### 3.2 Permissions decide what is visible

- After login the app calls `GET /api/v1/auth/me/` → `role`, `home_location`, `permissions` (list), `telegram_linked`.
- **Menus follow the role** (section 4). **Sensitive buttons follow permissions — hide them, don't disable them:**

| Permission | Shows | Default roles |
| --- | --- | --- |
| `view_personal_payments` | Personal-account amounts, lists, totals. Without it: the payment row exists, amount and account show "—" | everyone (D12) |
| `verify_payments` | Verify / Reject a payment | accountant |
| `correct_payments` | Reverse / Correct a payment | accountant |
| `correct_transactions` | Void a sale; reverse a goods-receipt movement | admin only (granted per accountant) |
| `approve_adjustments` | Approve / Reject stock adjustments | accountant |
| `approve_credit` | Confirm a sale beyond the customer's credit; edit credit terms | accountant |
| `approve_discounts` | Discounts above the owner's limit (P-84) | accountant |
| `export_reports` | **Export Excel** buttons | accountant |

Admins have every permission. The server enforces all of this anyway; hiding buttons is for clarity.

### 3.3 Money, quantities, dates

- **Money:** ETB, two decimals, thousands separators — `100,000.00 ETB`. The API sends money as strings (`"100000.00"`); never do money arithmetic in the browser — show what the API returns.
- **Quantities:** whole numbers with the unit (`pcs`, `set`).
- **Dates — Ethiopian first, Gregorian beside it (D16):** `ጥቅምት 26, 2019 (05/11/2026)`, time `14:35`, Addis Ababa time.
  - Documents in the API carry ready-made strings (`issued_at_ec`, `created_at_ec`, `date_ec`, `at_ec`, `period_label`); for anything else call `GET /api/v1/calendar/?date=YYYY-MM-DD` (or `?ec=YYYY-MM-DD`).
  - **Date pickers are Ethiopian:** 13 months (መስከረም … ነሐሴ, then ጳጉሜ with 5 or 6 days); send the Gregorian date the calendar endpoint returns.
- **No cost price, profit or margin anywhere (D1).**

### 3.4 Document numbers

`SO-2026-00125` sale · `DN-` delivery note · `SR-` stock request · `SRL-` release · `TR-` transfer · `GR-` goods receipt · `ADJ-` adjustment · `CC-` condition change · `PAY-` payment · `RET-` return · `MV-` movement.

- The **sale number (SO) is the transaction number (D4)** — every related request, release, transfer, delivery note and movement carries it. A request with no sale uses its own SR number.
- Every number is a **link** to its document; every transaction number also opens **Transaction history** (P-05).
- Numbers in a **monospace** font — people read them aloud on the phone.

### 3.5 Status chips — one colour per meaning, everywhere

| Object | Statuses |
| --- | --- |
| Stock request | Pending · Acknowledged · Partially released · Released · Closed · Rejected · Cancelled |
| Sale — fulfilment | Draft · Pending · Confirmed · Prepared · Partially released · Released · Cancelled · Voided |
| Sale — payment | Unpaid · Partial · Paid |
| Payment | Unverified · Verified · Rejected · Reversed |
| Transfer | In transit · Received, plus a **Short** warning when less arrived than was sent |
| Stock adjustment | Proposed · Approved · Rejected |
| Stock condition | New · Display · Damaged |
| Account kind | **Organization** and **Personal** — two strong, distinct colours, visible on every payment row (D3) |

Grey = not started · blue = in progress · green = done · amber = needs attention (unverified, partial, low stock, short, display/damaged) · red = rejected, cancelled, voided, reversed.

### 3.6 Errors, confirmations, empty states

- **Business errors:** `400 {"code": "...", "detail": "..."}` — show `detail` (already written for staff, e.g. "Only 3 VC-001 available at PIA.") in a banner or by the field. **Field errors:** `400 {"field": ["message"]}` under the field.
- `401` → back to login. `403` → "You don't have permission to do this." `404` → "Not found or not yours to see."
- **Every action that changes stock or money opens a confirmation** restating it ("Release 15 × VC-001 to Piassa?").
- **Reject, Cancel, Close, Void, Reverse, Correct and condition changes always ask for a reason** (required); the reason shows later in history.
- Lists: loading state, empty state ("No open requests 👍"), 25 per page (API pagination: `count`, `next`, `previous`, `results`).

### 3.7 Things that never appear

- **No delete** for anything that matters (products, users, locations, customers, sales, payments, movements). Things are deactivated, cancelled, voided or reversed.
- **No direct editing of stock numbers** — only through receipts, requests/releases, transfers, sales, returns, condition changes and approved adjustments.
- **No typed prices on a sale** — the price comes from the product (wholesale for resellers); a discount is the only adjustment.

---

## 4. Navigation per role

| Menu | Salesperson | Storekeeper | Accountant | Admin |
| --- | --- | --- | --- | --- |
| Home | ✓ | ✓ | ✓ | ✓ |
| New sale | ✓ | | ✓ | ✓ |
| Sales | own | sales it supplies | all | all |
| Payments | own | | all | all |
| Payments to verify | | | ✓ | ✓ |
| Customers & credit | ✓ | | ✓ | ✓ |
| Products | view | view | view | edit |
| Stock | ✓ | ✓ | ✓ | ✓ |
| Display & damaged | own branch | own warehouse | ✓ | ✓ |
| Stock requests | own branch | own warehouse | view all | all |
| Transfers | own location | own location | all | all |
| Goods receipts | | own warehouse | ✓ | ✓ |
| Stock adjustments | | propose | approve | ✓ |
| Stock movements | | own location | all | all |
| Reports | own sales | stock, movements, open requests | all | all |
| Audit log | | | view | ✓ |
| Users & permissions · Locations · Payment accounts · Settings | | | | ✓ |
| My profile | ✓ | ✓ | ✓ | ✓ |

---

## 5. Shared components (design once, use everywhere)

| Component | Behaviour |
| --- | --- |
| **Product picker** | Type a code or name → suggestions with code, name, price (wholesale when the customer is a reseller) and stock at the relevant locations. `GET /products/?search=` + `GET /products/{id}/stock/` |
| **Customer picker** | Search name / phone / shop; a **Walk-in customer** shortcut; **+ New customer** opens P-62 in a side panel. `GET /customers/?search=` |
| **Ethiopian date picker** | Month grid of 30 days (Pagume 5–6), Ethiopian year; shows the Gregorian date beneath. `GET /calendar/` |
| **Period picker** | Today · This week · This month · This year (Ethiopian months/years, with a Gregorian switch) · Custom range |
| **Money display / input** | `100,000.00 ETB`; input accepts digits and one decimal point, two decimals max |
| **Quantity stepper** | − / + with a typed value; shows the maximum allowed ("of 20") |
| **Reason dialog** | Required text, shows what will happen, Confirm / Cancel |
| **Confirm dialog** | Restates the action, quantities and locations |
| **Document link** | Monospace number, opens the document; transaction numbers also offer History |
| **Status chip** | Section 3.5 |
| **Account-kind badge** | Organization / Personal, always together with the account name |
| **Stock cell** | On hand, with small badges for reserved, display, damaged; hover shows available |

---

## 6. Page list

| # | Page | Users |
| --- | --- | --- |
| P-01 | Login | all |
| P-02 | Home dashboard (per role) | all |
| P-03 | My profile & Telegram link | all |
| P-04 | Search results | all |
| P-05 | Transaction history | all |
| P-10 | Products | all |
| P-11 | Product detail | all |
| P-12 | Product create / edit | admin |
| P-13 | Change price (dialog) | admin |
| P-14 | Import products | admin |
| P-20 | Stock overview (matrix) | all |
| P-21 | Low stock | all |
| P-22 | Stock movements | storekeeper, accountant, admin |
| P-23 | Goods receipts | storekeeper, accountant, admin |
| P-24 | Stock adjustments | storekeeper (propose), accountant, admin |
| P-25 | Transfers (list, detail, receive) | all |
| P-26 | New manual transfer | accountant, admin |
| P-27 | Display & damaged stock | staff at the location, accountant, admin |
| P-30 | Stock requests | salesperson, storekeeper, accountant, admin |
| P-31 | New stock request | salesperson, admin |
| P-32 | Stock request detail | all who can see it |
| P-33 | Release stock | storekeeper, admin |
| P-40 | New sale | salesperson, accountant, admin |
| P-41 | Sales list | salesperson (own), storekeeper (supplied), accountant, admin |
| P-42 | Sale detail | same |
| P-43 | Delivery note (print / PDF) | same |
| P-44 | Phone orders board | salesperson, storekeeper, accountant, admin |
| P-45 | Return goods · Void sale (dialogs) | accountant, admin · `correct_transactions` |
| P-50 | Record payment | salesperson (allowed accounts), accountant, admin |
| P-51 | Payments | salesperson (own), accountant, admin |
| P-52 | Payments to verify | `verify_payments` |
| P-53 | Payment detail | salesperson (own), accountant, admin |
| P-60 | Customers | salesperson, accountant, admin |
| P-61 | Customer detail & statement | same |
| P-62 | Customer create / edit | same; credit fields need `approve_credit` |
| P-70 | Reports (7) | per role |
| P-80 | Users & permissions | admin |
| P-81 | Locations | admin (others read) |
| P-82 | Payment accounts | admin (others read) |
| P-83 | Audit log | accountant (read), admin |
| P-84 | Settings | admin (everyone reads) |

---

## 7. Pages

### P-01 Login

- Username, password, **Log in**; company name/logo.
- Wrong username or password → `401` → "Wrong username or password." After 5 failures the account is locked for 30 minutes → `403 {"code": "account_locked"}` → "Too many failed attempts. Try again in 30 minutes."
- Access tokens last 15 minutes and refresh silently (refresh token 7 days) — users log in again only after a week away or after logging out.
- **API:** `POST /auth/token/ {username, password}` → `access`, `refresh` · `POST /auth/refresh/ {refresh}` · `GET /auth/me/`.

### P-02 Home dashboard

Short and actionable; every tile links to its filtered list.

| Role | Contents |
| --- | --- |
| Salesperson | Search box (product code → stock card) · **New sale** · my sales today (total, count) · my sales waiting for payment · my open stock requests · transfers arriving at my branch (Receive) · goods held at my branch for my customers |
| Storekeeper | **Request queue** — Pending, then Acknowledged / Partially released, newest first, with branch, customer, salesperson and lines (the main screen) · low stock · recent movements at my warehouse · my transfers not yet received |
| Accountant | Payments to verify (count + list) · today: sales, paid, credit, received Organization / Personal · adjustments to approve · transfers with shortages (last 30 days) · customers over their limit |
| Admin | The accountant's dashboard + low-stock products + today's sales by branch and salesperson |

**API:** `GET /dashboard/` — everything for the user's role in one call: `role`, then one block per tile, each `{count, items}` (the first 10; the tile links to its filtered list for the rest).

| Role | Blocks |
| --- | --- |
| Salesperson | `sales_today`, `waiting_for_payment`, `open_requests`, `transfers_arriving`, `held_for_customers` |
| Storekeeper | `request_queue` (Pending first), `low_stock`, `recent_movements`, `transfers_not_received` |
| Accountant | `payments_to_verify` (+ `total`), `today`, `adjustments_to_approve`, `transfers_with_shortages`, `customers_over_limit` |
| Admin | The accountant's blocks + `low_stock`; `today` adds `by_branch` and `by_salesperson` |

The tiles link to: `GET /orders/?payment_status=unpaid` · `GET /payments/?status=unverified` · `GET /stock-requests/?status=` · `GET /transfers/?status=in_transit&to_location=` · `GET /stock/summary/?low=true` · `GET /stock/movements/` · `GET /adjustments/?status=proposed` · `GET /customers/?over_limit=true`.

### P-03 My profile

- Name, username, role, home location, phone; the user's permissions with readable labels.
- **Telegram:** linked or not (`telegram_linked`). **Get link code** → an 8-character code, large and copyable, with "Send `/start CODE` to the bot within 10 minutes." **Unlink** (lost phone).
- **API:** `GET /auth/me/` · `POST /auth/telegram/link-code/` → `{code, expires_at}` · `POST /auth/telegram/unlink/` · `GET /permissions/`.

### P-04 Search results

The top-bar search accepts anything.

| Typed | Shows |
| --- | --- |
| Product code or name (`VC-001`) | **Product card first:** name, code, price (and wholesale), stock per location, in transit, total |
| Customer name, phone, shop | Customers with what they owe |
| SO / DN / SR / PAY number, or a customer's phone | The sale, delivery note, request or payment |
| Receipt number | The payment |

- When the API returns `exact`, jump straight to that page (product or document).
- Filters: salesperson, branch, from, to. Results respect the user's scope (a salesperson never sees others' sales; Personal amounts follow the permission).
- **API:** `GET /search/?q=&salesperson=&branch=&from=&to=` → `exact`, `products`, `customers`, `orders`, `delivery_notes`, `stock_requests`, `payments`.

### P-05 Transaction history

"The same delivery paper everyone tracks" — opened from **any** related number (SO, DN, SR, SRL, TR, MV, PAY, RET).

- **Header:** transaction number, customer, salesperson, branch, receipt type, status chips, total · paid · remaining, "Replaces SO-…" when re-issued.
- **Products:** code, name, quantity, released, returned, source.
- **Timeline:** created · confirmed · prepared · stock requested · acknowledged · released · received (shortage in amber) · handed over (DN) · payment recorded (amount, Organization/Personal) · verified · rejected · reversed · corrected · returned · cancelled / voided · re-issued — each with **who, when (Ethiopian first, `at_ec`) and reason**, linking to its document.
- **API:** `GET /transactions/{number}/` (or `GET /orders/{id}/history/`) → `header`, `events`.

### P-10 Products

- **Columns:** code, name, category, unit, selling price, **wholesale price** (resellers; empty = selling price), min stock, active.
- **Filters:** search (code/name), category, active. Sort: code, name, price.
- **Actions:** row → P-11; admin: **New product**, **Import products**.
- **API:** `GET /products/?search=&category=&is_active=&ordering=` · `GET /categories/` · `GET /units/`.

### P-11 Product detail

- Code, name, category, unit, selling price, wholesale price, min stock, description, active.
- **Stock card:** per location on hand / reserved / display / damaged / available; in transit; total and **sellable** total; low-stock warning when sellable < min stock.
- **Price history:** date, **which price** (selling / wholesale), old → new, who, reason.
- **Recent movements** (stock staff): date, type, condition, qty, from → to, transaction.
- **Admin:** Edit · Change price · Deactivate.
- **API:** `GET /products/{id}/` · `/products/{id}/stock/` · `/products/{id}/price-history/` · `GET /stock/movements/?product=`.

### P-12 Product create / edit (admin)

- Code (stored in capitals, unique), name, category, unit, selling price and optional wholesale price (**set on create only**), min stock, description, active.
- On edit both prices are read-only with a **Change price** button next to each (P-13).
- Errors: price ≤ 0; wholesale above selling (`wholesale_above_selling`); duplicate code.
- **API:** `POST /products/` · `PATCH /products/{id}/`.

### P-13 Change price (dialog, admin)

- Which price (selling / wholesale), current value, new value, reason.
- New value > 0 and different; wholesale never above selling — to lower the selling price below the wholesale price, lower the wholesale price first. "Sales already made keep their price."
- **API:** `POST /products/{id}/change-price/ {price_type, new_price, reason}`.

### P-14 Import products (admin)

- **Download template** → upload the filled `.xlsx` → **Check** (dry run: "would create 120, update 4, change 3 prices") → row errors if any ("row 7: unknown unit 'boxes'") → **Import**. One bad row stops the whole import.
- Template columns: Code, Name, Category, Unit, Price, Wholesale price, Min stock, Description.
- **API:** `GET /products/import-template/` → the `.xlsx` template · `POST /products/import/` (multipart: `file`, `dry_run=true` for **Check**) → `{dry_run, created, updated, price_changed, unchanged}`; on any error `400 {"code": "import_failed", "detail", "errors": ["row 7: unknown unit 'boxes'", …]}` and nothing is saved. Admin only; `.xlsx` up to 5 MB.

### P-20 Stock overview (matrix)

The client's "Current stock" table.

| Product | Piassa | Underground | Denbel | Pawlos | In transit | **Total** | Sellable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VC-001 Visitor chair | 25 *(1 display)* | 0 | 5 | 85 *(5 reserved)* | 0 | **115** | 114 |

- Each cell: on hand, with small badges for **reserved**, **display**, **damaged**; hover shows available.
- **Total includes In transit (D7).** **Sellable** excludes display and damaged (D15). Low-stock rows (sellable < min) highlighted.
- Filters: search, category, low only. Paginated by product. Export Excel (`export_reports`, via P-70 Stock).
- **API:** `GET /stock/summary/?search=&category=&low=true` → `locations` (column order) and `results[]`: `stock[code] = {on_hand, reserved, display, damaged, available}`, `in_transit`, `total`, `total_new`, `low_stock`.

### P-21 Low stock

P-20 with `low=true`, plus each product's minimum and the shortfall (min − sellable). [Q18: minimum per location?]

### P-22 Stock movements

- **Columns:** date (EC first), MV number, type (Receipt · Transfer out · Transfer in · Sale · Return · Adjustment · Reversal), **condition**, product, qty, from, to, customer, person, transaction, note.
- **Filters:** product, location, type, transaction, from, to; search. Storekeepers see their own location only.
- **Reverse** — only on goods-receipt movements, with `correct_transactions` and a reason. Other movements are corrected through their document; don't show the button.
- **API:** `GET /stock/movements/?product=&location=&type=&transaction=&from=&to=` · `POST /stock/movements/{id}/reverse/ {reason}`.

### P-23 Goods receipts

Imported goods arriving (usually at Pawlos). [Q1]

- **List:** GR number, date, location, reference (container / invoice), received by.
- **New:** location (default Pawlos; storekeepers only their own), reference, date received, note, lines (product picker + quantity; one line per product).
- Confirm: "Add 40 × VC-001, 12 × DS-003 to Pawlos?"
- **API:** `GET/POST /goods-receipts/ {location?, reference, received_at?, note, lines:[{product, qty}]}`.

### P-24 Stock adjustments

Counts, damage, loss, found items, opening balances, write-offs.

- **List:** ADJ number, date, location, product, change (+/− coloured), condition, reason, status, proposed by, decided by.
- **Propose** (storekeeper at own location, accountant, admin): location, product, change, **condition** (new / display / damaged — e.g. write off 2 damaged chairs: −2, damaged), reason (count, damage, loss, found, opening balance), note.
- **Approve / Reject** (`approve_adjustments`; reject needs a note). **Nobody approves their own proposal** except an admin — hide Approve on your own rows. Nothing moves until approved: say "Waiting for approval".
- **API:** `GET/POST /adjustments/` · `POST /adjustments/{id}/approve/ {note}` · `…/reject/ {note}`.

### P-25 Transfers

- **List:** TR number, sent, from → to, status, **Short**, transaction, linked request. Tabs: Incoming · Outgoing · All (accountant/admin).
- **Detail:** lines with condition, qty sent, qty received; discrepancy note.
- **Receive** (staff at the destination): each line defaults to the full quantity; lower it if fewer arrived ("2 still in transit — the accountant will be told"). Received once only. Goods for a sale are then **held** at the branch for that customer.
- **API:** `GET /transfers/?status=&from_location=&to_location=` · `GET /transfers/{id}/` · `POST /transfers/{id}/receive/ {lines:[{line_id, qty}]}` (empty body = all arrived).

### P-26 New manual transfer (accountant, admin)

Moves stock without a request (e.g. Piassa → Denbel, or a damaged piece to Pawlos for repair). [Q3]

- From, to (different, never In Transit), lines (product, qty, **condition**), note.
- **API:** `POST /transfers/ {from_location, to_location, lines:[{product, qty, condition}], note}`.

### P-27 Display & damaged stock (D15)

- **List:** CC number, date, location, product, qty, from → to condition, reason, who. Staff see their own location.
- **New change** (staff at that location, accountant, admin): location, product, qty, from, to, reason (required); show how many of the "from" condition are free there.
- Quick actions: **Put on display** · **Mark damaged** · **Back to new** (repaired / off display).
- Display and damaged pieces stay in the location's total but are never reserved or sold as new; they are sold as such on P-40 (usually with a discount), written off on P-24, sent for repair on P-26.
- **API:** `GET/POST /stock/condition-changes/ {product, location, qty, from_condition, to_condition, reason}`.

### P-30 Stock requests

The digital delivery paper from a branch to Pawlos.

- **Columns:** SR number, date, branch, customer / reference, salesperson, lines ("20 × VC-001, 2 × DS-003"), status, released / requested, transaction (SO when it serves a sale).
- **Scope:** salespeople their branch; storekeepers their warehouse; accountant/admin all.
- **Storekeeper default:** Pending first, then Acknowledged and Partially released — the work queue. A visual/sound cue for new requests is welcome.
- **Filters:** status, branch, source, customer, salesperson; search (number, transaction, reference, customer, product code).
- **API:** `GET /stock-requests/?status=&requesting_location=&source_location=&customer=&salesperson=&search=`.

### P-31 New stock request (salesperson, admin)

For restocking the branch. (Requests for a customer's sale are created automatically by P-40.)

- Branch (default mine; salespeople can't change it), source (default Pawlos), customer (optional; needed for pickup at Pawlos), reference, notes, lines (product picker showing **available at Pawlos**, quantity).
- Quantity can't exceed what's free at Pawlos ("Only 12 VC-001 available at PAW."). Storekeepers can't create requests.
- After saving: the SR number in large type.
- **API:** `POST /stock-requests/ {requesting_location?, source_location?, customer?, reference, notes, lines:[{product, qty}]}`.

### P-32 Stock request detail

- **Header:** SR number, transaction, status, branch → source, customer, reference, salesperson, created / acknowledged / closed (who, when, reason).
- **Lines:** product, requested, released, **remaining**.
- **Releases:** each SRL — date, destination (To branch / Customer pickup), lines, who, transfer number and its status.
- **Actions:**

| Status | Storekeeper (source) | Requesting salesperson | Admin |
| --- | --- | --- | --- |
| Pending | Acknowledge · Reject | Cancel | all |
| Acknowledged | Release · Reject | Cancel | all |
| Partially released | Release · Close | Close | all |
| Released | Close | Close | all |
| Rejected / Cancelled / Closed | — | — | — |

- Reject, Cancel, Close need a reason. Show only valid buttons (no release before acknowledge).
- **API:** `GET /stock-requests/{id}/` · `POST …/acknowledge/` · `…/release/` · `…/reject/ {reason}` · `…/cancel/ {reason}` · `…/close/ {reason}`.

### P-33 Release stock (storekeeper) — phone first

1. Each open line: quantity taken out now — default the remaining, **All**, **− / +**; 0 skips the line.
2. **Destination:** **To branch** (the branch must receive it) or **Customer pickup** (only when the request names a customer).
3. Optional note.
4. Summary → **Confirm** → release number (SRL) and, for branch, transfer number (TR).

**API:** `POST /stock-requests/{id}/release/ {destination_type: "branch"|"customer_pickup", lines:[{line_id, qty}], note}`.

### P-40 New sale — the most-used screen; fast at the counter

1. **Customer** (picker; **Walk-in** in one click; + New). Show type, credit allowed, limit and what they owe.
2. **Channel:** Walk-in or Phone order (phone orders start as Pending).
3. **Lines:** product picker → price **for this customer** (resellers get wholesale, labelled "Wholesale"), stock here and at Pawlos; quantity; **source** "From this branch" (taken now) or "From Pawlos" (a stock request is created on confirm); **condition** new / display / damaged (display and damaged only from this branch); **discount** per line in ETB (above the owner's limit needs `approve_discounts`). No price typing.
4. **Receipt type:** Official receipt · Without receipt.
5. **Pay now (optional):** account (only the user's allowed accounts; an official-receipt sale offers **Organization only**), amount, method, receipt number (required for Organization on an official sale, one per payment; never for Personal).
6. **Totals:** total · paid now · remaining (credit).
7. **Confirm.** A remaining balance needs a customer with credit within their limit, unless the user has `approve_credit` — show the reason clearly ("ABC Furniture would owe 160,000, above their limit of 150,000").

After confirm: the SO number large · delivery note button(s) · what happens next ("20 × VC-001 requested from Pawlos — SR-…").

**API:** `POST /orders/ {customer, branch?, channel, receipt_type, notes, lines:[{product, qty, discount, source_location?, condition}], payment?: {account, amount, method, receipt_number?, paid_at?, note?}}` → draft/pending; `PATCH /orders/{id}/` while draft/pending; `POST /orders/{id}/confirm/`.

### P-41 Sales list

- **Columns:** SO number, date (EC first), customer, branch, salesperson, channel, total, paid, remaining, fulfilment, payment, receipt type.
- **Scope:** salespeople only their own (D9); storekeepers the sales their warehouse supplies.
- **Filters:** number, status, payment status, customer, branch, salesperson, channel, receipt type, from, to; search (number, customer name or phone).
- **API:** `GET /orders/?number=&status=&payment_status=&customer=&branch=&salesperson=&channel=&receipt_type=&from=&to=&search=`.

### P-42 Sale detail

- **Header:** SO number, chips, customer (link), branch, salesperson, channel, receipt type, dates; "Replaces / Replaced by SO-…".
- **Lines:** product, condition, qty, unit price, discount, line total, source, released, **held at branch** (arrived, waiting for the customer), returned, **paid for this line**, remaining.
- **Totals:** total · paid · remaining.
- **Payments** (the client's table): date, PAY number, amount, **Organization / Personal**, account, status, recorded by.
- Delivery notes, stock requests and returns of this sale. **History** tab = P-05.
- **Actions by status and permission:** Edit (draft/pending) · Confirm · Record payment (P-50) · **Hand over at branch** (held goods first, then free branch stock) · **Request remaining stock** (after a rejected or short request) · Mark prepared (storekeeper) · Cancel (before any handover, reason) · Return goods (P-45) · Void (P-45) · Print delivery notes.
- **API:** `GET /orders/{id}/` · `GET /orders/{id}/payments/` · `GET /orders/{id}/history/` · `POST …/confirm/` · `…/release-from-branch/ {lines:[{line_id, qty}]}` · `…/request-stock/ {lines:[{line_id, qty}]}` · `…/status/ {"status": "prepared"}` · `…/cancel/ {reason}` · `…/return/` · `…/void/ {reason}`.

### P-43 Delivery note (print / PDF)

Replaces the three-copy paper pad. One per handover (branch, or pickup at Pawlos), so a sale can have several.

- A4 portrait, black-and-white friendly: **SO number in large type**, DN number, **date Ethiopian first** (`መስከረም 26, 2019 (06/10/2026) 16:36`), from (location), customer (name, shop, phone, city), salesperson, receipt type, table (code, product, qty, unit price, total), sale total / paid / remaining, signature lines: salesperson · storekeeper · customer. [Q10: VAT; Q13: match the current paper.]
- **API:** `GET /delivery-notes/?order={id}` · `GET /delivery-notes/{id}/pdf/` (the PDF is rendered by the server; show it in a viewer with Print).

### P-44 Phone orders board

Out-of-city orders: **Pending → Confirmed → Prepared → Released**.

- Columns or grouped list by status: customer, city, lines, payment status, request status.
- Storekeeper marks **Prepared**; release happens on the request (customer pickup). **No company delivery (D8)** — never a "Shipping / Delivered" step.
- **API:** `GET /orders/?channel=phone&status=` · `POST /orders/{id}/status/ {"status": "prepared"}`.

### P-45 Return goods · Void sale (dialogs)

- **Return goods** (accountant, admin): lines and quantities (each back as **new or damaged**), receiving location, reason. The sale total drops; money paid beyond the new total becomes the customer's credit. [Q7]
  **API:** `POST /orders/{id}/return/ {location, reason, lines:[{line_id, qty, condition}]}`.
- **Void sale** (`correct_transactions`): for a sale entered wrongly — "Stock goes back, the sale leaves the customer's balance, its payments become the customer's credit." Reason required. Then **Re-issue corrected sale** opens P-40 pre-filled and linked (`replaces`). Not possible after a return.
  **API:** `POST /orders/{id}/void/ {reason}` · `POST /orders/ {…, replaces: <id>}`.

### P-50 Record payment

From a sale, a customer, or the menu.

- Customer, amount, account (salespeople: only their allowed accounts, only for their own sales), method (bank / cash / mobile money), receipt number (Organization only), date-time paid, note.
- **Allocation:** to specific sales and/or specific lines ("For: 10 chairs"), showing each sale's and line's remaining. Unallocated money stays the customer's **advance** until the accountant allocates it (Q20).
- **Live checks:** not more than the payment, a sale's remaining or a line's remaining; official sale + Personal → blocked; Personal + receipt → blocked; a receipt number already used → blocked.
- Salespeople's payments start **Unverified**; the accountant's are verified at once.
- **API:** `POST /payments/ {customer, account, amount, method, receipt_number?, paid_at?, note, allocations:[{order, line?, amount}]}`.

### P-51 Payments

- **Columns:** PAY number, date (EC first), customer, amount, account, **kind**, method, receipt, status, recorded by, allocated to.
- **Totals bar:** Organization · Personal · Combined for the current filters (from P-70 Payments).
- **Filters:** number, receipt number, account, kind, status, customer, sale, salesperson, branch, recorded by, from, to; search.
- Salespeople: payments they recorded or that pay their sales.
- **API:** `GET /payments/?number=&receipt_number=&account=&account_kind=&status=&customer=&order=&salesperson=&branch=&recorded_by=&from=&to=&search=`.

### P-52 Payments to verify (`verify_payments`)

- Queue of unverified payments, oldest first: amount, account and kind, receipt, customer, sale, recorded by.
- **Verify** (one click) · **Reject** (reason: e.g. "not on the bank statement"). Bulk verify welcome.
- **API:** `GET /payments/?status=unverified&ordering=paid_at` · `POST /payments/{id}/verify/` · `…/reject/ {reason}`.

### P-53 Payment detail

- Everything recorded, the allocations (active and released, with why), and the permanent history: recorded → verified / rejected / reversed / corrected, each with who and when; "Corrects PAY-…" / "Corrected by PAY-…".
- **Actions:** Verify / Reject (`verify_payments`) · **Correct** (`correct_payments`: new amount, account, method, date or receipt; reverses the old one and links them) · Reverse (`correct_payments`, reason) · Allocate advance / **Pay oldest first** (accountant, admin).
- **API:** `GET /payments/{id}/` · `POST …/verify/` · `…/reject/ {reason}` · `…/reverse/ {reason}` · `…/correct/ {reason, amount?, account?, method?, receipt_number?, paid_at?, allocations?}` · `…/allocate/ {allocations}` · `…/allocate-oldest-first/`.

### P-60 Customers

- **Columns:** name, shop, phone, city, type (Walk-in / Reseller / Out-of-city), credit allowed, credit limit, **owes** (`outstanding`), with an amber **Over limit** chip when `over_limit` (owes without credit allowed, or more than the limit).
- **Filters:** search (name, phone, shop), type, city, credit allowed, active, **has a balance**, **over their limit**. Sort by name or by what they owe.
- **New customer** (salespeople can).
- **API:** `GET /customers/?search=&type=&city=&credit_allowed=&is_active=&has_balance=&over_limit=&ordering=-outstanding` — each row has `outstanding` and `over_limit`.

### P-61 Customer detail & statement

The client's example: "ABC Furniture — Total purchases 500,000 · Payments 350,000 · Outstanding 150,000".

- **Summary:** total purchases, total paid, **outstanding**, prepaid, unallocated (advance), credit allowed, limit.
- **Statement:** date (`date_ec`), document, debit, credit, **running balance**; payments show Organization / Personal. Date range (Ethiopian picker), print.
- Tabs: sales · payments · stock requests. Actions: Record payment · New sale · Edit.
- **API:** `GET /customers/{id}/` · `/customers/{id}/balance/` · `/customers/{id}/statement/?from=&to=` → `opening_balance`, `rows`, `closing_balance`.

### P-62 Customer create / edit

- Name, phone, shop / company, city, type, notes; **credit allowed** and **credit limit** (editable only with `approve_credit`).
- A phone already used by another customer is a **warning**, not an error (the API returns `warnings`).
- **API:** `POST /customers/` · `PATCH /customers/{id}/`.

### P-70 Reports

Each report: period picker, filters, totals, table, **Export Excel** (`export_reports`). The daily, weekly, monthly and yearly sales reports also reach the owner by Telegram.

| Report | Shows | Filters |
| --- | --- | --- |
| **Sales** | Sales, returns, net sales, transactions; paid vs still owed (credit); official vs no receipt; money received Organization / Personal / Combined; by branch; by salesperson; products and quantities; best sellers; a 13-row Ethiopian month table for a year | period, branch, salesperson, customer, category |
| **Payments** | Organization, Personal, Combined, grouped by day / week / Ethiopian month / year; the payment list | period, customer, account, account kind, sale, salesperson, branch; group by |
| **Credit** | Outstanding per customer, aged 0–30 / 31–60 / 61–90 / 90+ days; total outstanding; credit collected in the period | period, customer |
| **Stock** | The P-20 matrix with display, damaged, sellable, minimum, low flag | category |
| **Movements** | Every movement with condition, transaction, reference, person | period, product, location, type |
| **Open requests** | Requests not finished and how long they've waited | — |
| **Unverified payments** | Payments waiting for the accountant | — |

- **Who:** salespeople — Sales (own figures only); storekeepers — Stock, Movements, Open requests (their location); accountant and admin — all. Personal figures need `view_personal_payments`.
- **Period:** Today · This week (Mon–Sun) · This month · This year — **Ethiopian months and years by default (D16)**, Gregorian on request — or a from–to range. Show the returned `period_label`.
- **API:** `GET /reports/{sales|payments|credit|stock|movements|open-requests|unverified-payments}/?period=day|week|month|year&date=&calendar=ethiopian|gregorian` or `?from=&to=`; filters as above; `&group_by=` (payments); `&format=xlsx` downloads Excel.

### P-80 Users & permissions (admin)

- **List:** name, username, role, home location, Telegram linked, active.
- **Create / edit:** username, full name, phone, role, home location (needed for salespeople and storekeepers), active, password (set / reset), **permissions** (checkboxes with labels and default roles), **allowed payment accounts** (for salespeople).
- A new user gets the role's default permissions; **changing the role resets them** — warn before saving. Admins have everything (show ticked and locked). Deactivate, never delete. Every change is audited.
- **API:** `GET/POST /users/` · `PATCH /users/{id}/ {…, permissions:[…], allowed_payment_accounts:[ids]}` · `GET /permissions/`.

### P-81 Locations (admin; others read)

- Code, name, type (shop / warehouse / sub-store), parent, can sell, can release, active.
- **In Transit** is a system location: shown, never editable.
- **API:** `GET/POST/PATCH /locations/`.

### P-82 Payment accounts (admin; others read)

- Name, **kind (Organization / Personal)**, method (bank / cash / mobile money), bank name, account number, owner name, active. The owner enters the real accounts once live (Q8).
- Salespeople only ever see the accounts they're allowed (set on P-80).
- **API:** `GET/POST/PATCH /payment-accounts/`.

### P-83 Audit log (accountant read, admin)

"Who changed what, and when" for every important change.

- **Columns:** date-time, who, action (price change, user updated, adjustment approved, payment reversed, …), object (type + number/name, linked), before → after (readable), reason, source (web / bot / system), IP.
- **Filters:** object type (`model`), object id, person, action, source, from, to. Read-only.
- **API:** `GET /audit/?model=&object_id=&actor=&action=&source=&from=&to=`.

### P-84 Settings (admin; everyone reads)

- **Salesperson discount limit (%)** — set by the owner (D13); starts at 0% (every discount needs approval). Show who changed it last and when.
- Room for later settings (company name and address on the delivery note, …).
- **API:** `GET /settings/` · `PATCH /settings/ {max_salesperson_discount_pct}`.

---

## 8. Backend gaps for the frontend

None. The three gaps listed here earlier are closed:

| Page | Now |
| --- | --- |
| P-14 Import products | `GET /products/import-template/` and `POST /products/import/` (check + import) |
| P-60 Customers, P-02 accountant | `outstanding` and `over_limit` on every customer; filters `has_balance`, `over_limit`; sort `ordering=-outstanding` |
| P-02 dashboards | `GET /dashboard/` — one call per page load |

---

## 9. Open client questions that affect the design

| Question | What may change |
| --- | --- |
| Q4, Q18 | Whether Underground is its own stock column; low-stock minimum per location |
| Q7 | How returns work today (P-45) |
| Q10, Q13 | VAT on official-receipt notes; the delivery note layout (send a photo of the current paper) |
| Q16 | An "Approved" step before the storekeeper may release (P-32) |
| Q19 | Transaction prefix: `SO-` or the client's `PS-` |
