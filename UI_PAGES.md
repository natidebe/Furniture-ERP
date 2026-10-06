# Furniture ERP — Web UI Page Requirements

**For:** the designer and the frontend developer.
**Based on:** `userequirements.md`, the decisions D1–D10 in `BUILD_PHASES.md`, and the backend API in `backend/`.
**Last updated:** 6 Oct 2026 (owner's answers to Q6, Q8, Q9, Q11, Q14, Q15, Q20)

Every page below lists who uses it, what it shows, what the user can do, the rules the screen must respect, and the API it calls. **Phase** says when the backend for it exists:

- **Ready** — built in Phase 1–2; it can be designed and wired now.
- **P3** — sales, payments, customers, search and transaction history (Phase 3).
- **P4** — reports and Excel export (Phase 4).

Until the client answers the open questions (Q1–Q20 in `BUILD_PHASES.md` 1.9), design for the current assumptions. Places marked **[Q…]** may change.

---

## 1. Who uses the system

| Role | Works at | Main jobs on the web |
| --- | --- | --- |
| Salesperson | Piassa or Denbel branch | Sell, check stock and prices, create customers, request stock from Pawlos, record payments they are allowed to, follow their own orders and sales |
| Storekeeper | Pawlos warehouse | See requests, release stock (record the quantity actually released), receive imports, propose stock corrections, view warehouse stock and history |
| Accountant | Office | See all sales and stock movements, record and verify payments, manage credit, approve stock corrections, run reports and Excel exports |
| Admin (owner) | Anywhere | Everything above, plus products, prices, users and their permissions, locations, payment accounts, audit log |

Locations: **Piassa (PIA)**, **Piassa Underground (PIA-UG)**, **Denbel (DEN)**, **Pawlos warehouse (PAW)**, and the system location **In Transit** (goods between locations). [Q4, Q18: Underground may be merged with Piassa.]

The bot (Telegram) only notifies and does quick actions. **All selling and payment entry happens on the web (D10).**

---

## 2. Global rules for every page

### 2.1 Layout

- **Desktop first** (the shop counter and office use PCs), but every page must work on a **tablet** (1024 px) and the storekeeper pages on a **phone** (360 px) — the Pawlos storekeeper may release from the floor.
- **Left sidebar** with the role's menu (section 3). Collapsible on small screens.
- **Top bar:** global search box (always visible), the user's name, role and home location, a link to **My profile**, and **Log out**.
- Page header: title, the main action button on the right (for example **New sale**), then filters, then content.

### 2.2 What each user may see and do

- After login the app calls `GET /api/v1/auth/me/`, which returns `role`, `home_location` and `permissions` (a list).
- **Menus** follow the role (section 3).
- **Buttons for sensitive actions** show only when the user has the permission. Hide them rather than disabling them, so salespeople aren't shown buttons they can never use:

| Permission | Shows / enables |
| --- | --- |
| `view_personal_payments` | Personal-account amounts, totals and report columns. **Every staff member has it by default (D12)**; the admin can remove it from one user — then show the payment exists and its status, with amount and account hidden (show "—"). |
| `verify_payments` | Verify / Reject buttons on payments |
| `correct_payments` | Reverse / Correct buttons on payments |
| `correct_transactions` | Void sale; Reverse movement |
| `approve_adjustments` | Approve / Reject on stock adjustments |
| `approve_credit` | Can confirm a sale beyond a customer's credit rules; can edit a customer's credit settings |
| `approve_discounts` | Discounts above the salesperson limit the owner sets in Settings (P-84) |
| `export_reports` | **Export Excel** buttons |

Admins have every permission.

### 2.3 Numbers, money and dates

- Money: **ETB**, two decimals, thousands separator: `100,000.00 ETB`. The API sends money as text (`"100000.00"`) — never round it in the browser.
- Quantities are whole numbers. Show the unit (`pcs`, `set`).
- Dates: `03/10/2026` (day/month/year) and time `14:35`, in Addis Ababa time. [Q12: Ethiopian calendar and Amharic may be required on screens and/or printouts — keep room for a second date line and for longer labels.]
- **There is no cost price, profit or margin anywhere (D1).** Do not design fields for them.

### 2.4 Document numbers (D4)

Every document has a number: `SO-2026-00125` (sale), `DN-` (delivery note), `SR-` (stock request), `SRL-` (release), `TR-` (transfer), `GR-` (goods receipt), `ADJ-` (adjustment), `PAY-` (payment), `MV-` (stock movement).

- The **sale number (SO) is the transaction number**: every related document shows it. A stock request with no sale uses its own SR number.
- Every document number on every page is a **link** to that document, and every transaction number is a link to its **Transaction history** page (P-05).
- Show numbers in a monospace font so they're easy to read aloud on the phone.

### 2.5 Status chips (one colour per meaning, used everywhere)

| Object | Statuses (in order) |
| --- | --- |
| Stock request | Pending · Acknowledged · Partially released · Released · Closed · Rejected · Cancelled |
| Sale (fulfilment) | Draft · Pending · Confirmed · Prepared · Partially released · Released · Cancelled · Voided |
| Sale (payment) | Unpaid · Partial · Paid |
| Payment | Unverified · Verified · Rejected · Reversed |
| Transfer | In transit · Received (+ "Short" warning when less arrived than was sent) |
| Stock adjustment | Proposed · Approved · Rejected |
| Payment account kind | **Organization** and **Personal** — two strong, different colours; this difference must be obvious on every payment row (D3) |

Suggested colour meaning: grey = not started, blue = in progress, green = done, amber = needs attention (unverified, partial, low stock, short receipt), red = rejected/cancelled/voided/reversed.

### 2.6 Errors, confirmations and empty states

- The API returns business errors as `400 {"code": "...", "detail": "..."}`. Show `detail` in a clear message next to the form or as a banner. It is already written for staff ("Only 3 VC-001 available at PIA.").
- Field errors come as `400 {"field_name": ["message"]}` — show them under the field.
- `403` → "You don't have permission to do this." `401` → back to login (session expired).
- **Every action that changes stock or money opens a confirmation** that repeats what will happen ("Release 15 × VC-001 to Piassa?").
- **Reject, Cancel, Close, Void, Reverse and Correct always ask for a reason** (required text box). The reason is shown later in the history.
- Lists have an empty state ("No open requests") and a loading state. Long lists are paginated (25 per page, from the API).

### 2.7 Things that never exist in the UI

- No **delete** for products, users, locations, customers, sales, payments, stock movements. Things are deactivated, cancelled, voided or reversed — never deleted.
- No direct edit of stock numbers. Stock changes only through receipts, requests/releases, transfers, sales, returns and approved adjustments.
- No editing a price inside a sale — the price always comes from the product (discount is the only adjustment).

---

## 3. Navigation per role

| Menu item | Salesperson | Storekeeper | Accountant | Admin |
| --- | --- | --- | --- | --- |
| Home (dashboard) | ✓ | ✓ | ✓ | ✓ |
| New sale | ✓ | | ✓ | ✓ |
| Sales / Orders | own only | | all | all |
| Payments | own only | | all | all |
| Payments to verify | | | ✓ | ✓ |
| Customers & credit | ✓ | | ✓ | ✓ |
| Products | view | view | view | edit |
| Stock (all locations) | ✓ | ✓ | ✓ | ✓ |
| Stock requests | own branch | own warehouse | all (view) | all |
| Transfers | own location | own location | all | all |
| Goods receipts | | own warehouse | ✓ | ✓ |
| Stock adjustments | | propose | approve | ✓ |
| Stock movements | | own location | all | all |
| Reports | own sales | stock | ✓ | ✓ |
| Audit log | | | view | ✓ |
| Users & permissions | | | | ✓ |
| Locations | | | | ✓ |
| Payment accounts | | | | ✓ |
| My profile | ✓ | ✓ | ✓ | ✓ |

---

## 4. Page list

| # | Page | Users | Phase |
| --- | --- | --- | --- |
| P-01 | Login | all | Ready |
| P-02 | Home dashboard (one per role) | all | Ready (stock parts) / P3 / P4 |
| P-03 | My profile (link Telegram) | all | Ready |
| P-04 | Global search results | all | P3 (products: Ready) |
| P-05 | Transaction history | all | P3 |
| P-10 | Products list | all | Ready |
| P-11 | Product detail | all | Ready |
| P-12 | Product create / edit | admin | Ready |
| P-13 | Change price (dialog) | admin | Ready |
| P-14 | Import products | admin | Ready (command; upload page needs an endpoint) |
| P-20 | Stock overview (matrix) | all | Ready |
| P-21 | Low stock | all | Ready |
| P-22 | Stock movements | storekeeper, accountant, admin | Ready |
| P-23 | Goods receipts list + New receipt | storekeeper, accountant, admin | Ready |
| P-24 | Stock adjustments list + Propose + Approve | storekeeper, accountant, admin | Ready |
| P-25 | Transfers list + detail + Receive | all | Ready |
| P-26 | New manual transfer | accountant, admin | Ready |
| P-27 | Display and damaged stock | staff at the location, accountant, admin | Ready |
| P-30 | Stock requests list | salesperson, storekeeper, accountant, admin | Ready |
| P-31 | New stock request | salesperson, admin | Ready |
| P-32 | Stock request detail (acknowledge, release, reject, cancel, close) | all | Ready |
| P-33 | Release stock (dialog / page) | storekeeper, admin | Ready |
| P-40 | New sale (counter sale and phone order) | salesperson, accountant, admin | P3 |
| P-41 | Sales / orders list | salesperson (own), accountant, admin | P3 |
| P-42 | Sale detail | all who can see it | P3 |
| P-43 | Delivery note (print / PDF) | salesperson, storekeeper, accountant, admin | P3 |
| P-44 | Phone orders board | salesperson, storekeeper, accountant, admin | P3 |
| P-45 | Return goods / Void sale (dialogs) | per permission | P3 |
| P-50 | Record payment | salesperson (allowed accounts), accountant, admin | P3 |
| P-51 | Payments list | salesperson (own), accountant, admin | P3 |
| P-52 | Payments to verify | accountant, admin | P3 |
| P-53 | Payment detail (verify, reject, reverse, correct, allocate) | accountant, admin | P3 |
| P-60 | Customers list | salesperson, accountant, admin | P3 |
| P-61 | Customer detail (balance, statement) | salesperson, accountant, admin | P3 |
| P-62 | Customer create / edit (credit settings) | salesperson; credit fields `approve_credit` | P3 |
| P-70 | Reports home + 7 reports | per role | P4 |
| P-80 | Users list + User create / edit (permissions) | admin | Ready |
| P-81 | Locations | admin | Ready |
| P-82 | Payment accounts | admin | P3 |
| P-83 | Audit log | accountant, admin | Ready |
| P-84 | Settings (discount limit) | admin | P3 |

---

## 5. Pages

### P-01 Login — Ready

- **Shows:** username, password, **Log in** button. Company name/logo.
- **Rules:** a wrong username or password returns `401` → show "Wrong username or password." After 5 wrong passwords the account is locked for 30 minutes and login returns `403 {"code": "account_locked"}` → show "Too many failed attempts. Try again in 30 minutes." Sessions use tokens that last 15 minutes and refresh automatically for 7 days; the user should only be asked to log in again after a week of inactivity or after logging out.
- **API:** `POST /api/v1/auth/token/` → `access`, `refresh`; `POST /api/v1/auth/refresh/`; then `GET /api/v1/auth/me/`.

### P-02 Home dashboard — one per role

Short, actionable. Every tile is a link to the filtered list behind it.

| Role | Tiles and lists |
| --- | --- |
| Salesperson | Quick search box (product code → stock card) · **New sale** button · My open stock requests (status) · Transfers arriving at my branch (to receive) · My sales today (total, count) [P3] · My orders waiting for payment [P3] |
| Storekeeper | **Requests waiting** (Pending, then Acknowledged/Partially released) — the main screen, newest first, with branch, customer, salesperson and lines · Warehouse stock alerts (low stock) · Recent movements at Pawlos · Outgoing transfers not yet received |
| Accountant | Payments to verify (count + list) [P3] · Today: sales, paid, credit, Organization vs Personal received [P3/P4] · Adjustments waiting for approval · Transfers with shortages · Customers over credit limit [P3] |
| Admin | Everything the accountant sees + low-stock products + today's sales by branch and by salesperson [P4] |

**API (Ready):** `GET /stock-requests/?status=…`, `GET /transfers/?status=in_transit`, `GET /stock/summary/?low=true`, `GET /stock/movements/`, `GET /adjustments/?status=proposed`.

### P-03 My profile — Ready

- **Shows:** name, username, role, home location, phone, the permissions the user has (readable names from `GET /permissions/`).
- **Link Telegram:** button **Get link code** → shows an 8-character code (large, copyable), and instructions: "Open the bot and send /start CODE. The code expires in 10 minutes." Show whether Telegram is already linked.
- **API:** `GET /auth/me/`, `POST /auth/telegram/link-code/` → `{code, expires_at}`, `GET /permissions/`.

### P-04 Global search results — P3 (products Ready)

The top-bar search accepts anything (requirement "Search"):

| Typed | Result group |
| --- | --- |
| Product code or name (`VC-001`, `visitor chair`) | **Product card first:** name, code, price, stock per location (Piassa, Underground, Denbel, Pawlos), in transit, **total** |
| Customer name, phone, shop name | Customers with outstanding balance |
| SO / DN / SR / SRL / TR / PAY / MV number | The document; transaction numbers open P-05 |
| Receipt number | The payment(s) |

- Filters on the results page: salesperson, branch, date from/to.
- An exact product code or document number jumps straight to its page.
- Personal-account payments are hidden from users without `view_personal_payments`.
- **API:** `GET /search/?q=&salesperson=&branch=&from=&to=` [P3]. Until then: `GET /products/?search=` and `GET /products/{id}/stock/`.

### P-05 Transaction history — P3

The digital version of "the same delivery paper everyone tracks". Opened from any number.

- **Header:** transaction number, customer, salesperson, branch, source → destination, status chips (fulfilment + payment), totals (total, paid, remaining).
- **Products:** code, name, quantity, released so far.
- **Timeline (newest at the bottom, or toggle):** created · confirmed · stock requested · acknowledged · released (qty) · transferred · received (shortages in amber) · delivery note issued · payment recorded (amount, **Organization/Personal**, who) · verified / rejected / reversed / corrected · voided · re-issued as … — each with **who, date-time and reason**.
- Links from every event to its document.
- **API:** `GET /transactions/{number}/` or `GET /orders/{id}/history/` [P3].

### P-10 Products list — Ready

- **Columns:** code, name, category, unit, selling price, **wholesale price** (what resellers pay; empty = same as selling), min stock, total stock (optional, from P-20), active.
- **Filters:** search (code or name), category, active/inactive. Sort by code, name, price.
- **Actions:** row → P-11. Admin: **New product**, **Import products**.
- **No cost price column (D1).**
- **API:** `GET /products/?search=&category=&is_active=&ordering=`, `GET /categories/`, `GET /units/`.

### P-11 Product detail — Ready

- **Shows:** code, name, category, unit, selling price, wholesale price, min stock, description, active.
- **Stock card:** per location on hand / reserved / available, In transit, Total, low-stock warning when total < min stock.
- **Price history:** date, **which price** (selling / wholesale), old price, new price, changed by, reason.
- **Recent movements** (for storekeeper/accountant/admin): date, type, qty, from → to, transaction number.
- **Admin actions:** Edit, Change price, Deactivate.
- **API:** `GET /products/{id}/`, `GET /products/{id}/stock/`, `GET /products/{id}/price-history/`, `GET /stock/movements/?product={id}`.

### P-12 Product create / edit — Ready (admin)

- **Fields:** code (stored in capitals; must be unique), name, category, unit, selling price and wholesale price (both create only; wholesale optional), min stock, description, active.
- **Rules:** on edit, both prices are **read-only** with a **Change price** button next to each (P-13). Prices must be > 0; the wholesale price cannot be higher than the selling price (error code `wholesale_above_selling`).
- **API:** `POST /products/`, `PATCH /products/{id}/`.

### P-13 Change price (dialog) — Ready (admin)

- **Fields:** which price (selling / wholesale), current value (read-only), new price, reason (optional but encouraged).
- **Rules:** new price > 0 and different from the current one; wholesale never above selling (lowering the selling price below the wholesale price is refused — lower the wholesale price first). Old sales keep their old price — say so in the dialog.
- **API:** `POST /products/{id}/change-price/ {price_type: "selling"|"wholesale", new_price, reason}`.

### P-14 Import products — Ready as a server command

- Page: **Download template** → upload the filled `.xlsx` → **Check file** (dry run: "would create 120, update 4, change 3 prices") → list of row errors if any ("row 7: unknown unit 'boxes'") → **Import**. Nothing is imported if any row has an error.
- **API:** today this is `manage.py import_products` on the server. A web upload needs a small endpoint — tell the backend before designing this page in detail.

### P-20 Stock overview (matrix) — Ready

The client's "Current stock" table.

| Product | Piassa | Underground | Denbel | Pawlos | In transit | **Total** |
| --- | --- | --- | --- | --- | --- | --- |
| VC-001 Visitor chair | 25 | 0 | 5 | 85 (5 reserved) | 0 | **115** |

- Each location cell shows **on hand**; small badges show **reserved** (held for requests or sales), **display** and **damaged** (D15); hover shows available (new stock free to sell).
- **Total includes In transit (D7).** A second total shows **sellable** stock (`total_new`, without display and damaged pieces). Low-stock rows (sellable < min stock) are highlighted.
- **Filters:** search, category, low stock only. Pagination by product.
- **Actions:** row → P-11. Export Excel [P4, `export_reports`].
- **API:** `GET /stock/summary/?search=&category=&low=true` → `locations` (column order) and `results` (rows: `stock[code].on_hand/reserved/available`, `in_transit`, `total`, `low_stock`).

### P-27 Display and damaged stock — Ready (D15)

- **List:** CC number, date, location, product, quantity, from → to (new / display / damaged), reason, who. Staff see their own location.
- **New change (staff at the location, accountant, admin):** location, product, quantity, from condition, to condition, reason (required). Shows how many of the "from" condition are free there.
- Common uses: **Put on display**, **Mark damaged**, **Back to new** (repaired / taken off display).
- **Writing off** damaged pieces is a stock adjustment with condition "damaged" (P-24, needs approval). **Sending for repair** is a transfer line with condition "damaged" (P-26).
- **API:** `GET/POST /stock/condition-changes/ {product, location, qty, from_condition, to_condition, reason}`.

### P-21 Low stock — Ready

Same as P-20 with `low=true`, plus the minimum per product and how many are missing (min − total). [Q18: minimum may become per location.]

### P-22 Stock movements — Ready

- **Columns:** date-time, MV number, type (Receipt, Transfer out, Transfer in, Sale, Return, Adjustment, Reversal), product, qty, from, to, customer, person, transaction number, note.
- **Filters:** product, location, type, transaction number, date from/to; search.
- **Scope:** storekeepers see only movements at their own location.
- **Action:** **Reverse** on goods-receipt movements only (`correct_transactions`; reason required). Other movements are corrected through their document — don't show the button.
- **API:** `GET /stock/movements/?product=&location=&type=&transaction=&from=&to=`, `POST /stock/movements/{id}/reverse/ {reason}`.

### P-23 Goods receipts — Ready

When imported goods arrive (usually at Pawlos). [Q1]

- **List:** GR number, date, location, reference (container/invoice no.), received by, number of lines.
- **New receipt form:** location (default Pawlos; storekeepers only their own), reference, date received, note, **lines** (product picker with code search + quantity; add/remove rows; one line per product).
- **Confirm:** "Add 40 × VC-001, 12 × DS-003 to Pawlos?"
- **API:** `GET/POST /goods-receipts/` — body `{location?, reference, received_at?, note, lines:[{product, qty}]}`.

### P-24 Stock adjustments — Ready

For counts, damage, loss, found items and opening balances.

- **List:** ADJ number, date, location, product, change (+/−, coloured), reason, status, proposed by, decided by.
- **Propose form (storekeeper at own location, accountant, admin):** location, product, change (positive adds, negative removes), **condition** (new / display / damaged — e.g. write off damaged pieces), reason (count, damage, loss, found, opening balance), note.
- **Approve / Reject (`approve_adjustments`):** approve note optional, reject note required. **You cannot approve your own proposal** unless you are admin — hide Approve on your own rows.
- Nothing moves until approved — say "Waiting for approval" clearly.
- **API:** `GET/POST /adjustments/`, `POST /adjustments/{id}/approve/ {note}`, `POST /adjustments/{id}/reject/ {note}`.

### P-25 Transfers — Ready

- **List:** TR number, date sent, from → to, status, transaction number, linked stock request, **Short** warning.
- **Tabs:** Incoming (to my location) · Outgoing · All (accountant/admin).
- **Detail:** lines with qty sent and qty received; discrepancy note.
- **Receive (staff at the destination):** each line defaults to the full quantity; staff can lower it if fewer arrived. Show "2 still in transit — the accountant will be told" before confirming. A transfer can be received once.
- **API:** `GET /transfers/?status=&from_location=&to_location=`, `GET /transfers/{id}/`, `POST /transfers/{id}/receive/ {lines:[{line_id, qty}]}` (empty body = everything arrived).

### P-26 New manual transfer — Ready (accountant, admin)

Moves stock between locations without a stock request (for example Piassa → Denbel). [Q3]

- **Fields:** from, to (not the same; never In Transit), lines (product + qty + condition: new, display or damaged — e.g. a damaged piece sent to Pawlos for repair), note.
- **API:** `POST /transfers/ {from_location, to_location, lines, note}`.

### P-30 Stock requests list — Ready

The digital delivery paper from a branch to Pawlos.

- **Columns:** SR number, date, requesting branch, customer / reference, salesperson, lines summary ("20 × VC-001, 2 × DS-003"), status, released / requested.
- **Scope:** salesperson — own branch; storekeeper — own warehouse; accountant/admin — all.
- **Storekeeper default view:** Pending first, then Acknowledged and Partially released (the work queue). Sound/visual highlight for new requests is welcome.
- **Filters:** status, branch, customer, salesperson; search (number, reference, customer, product code).
- **API:** `GET /stock-requests/?status=&requesting_location=&source_location=&customer=&salesperson=&search=`.

### P-31 New stock request — Ready (salesperson, admin)

The requirement's request content: date, requesting branch, product name, code, quantity, customer/order reference, salesperson, notes.

- **Fields:** requesting branch (default: my branch; salespeople cannot change it), source (default Pawlos), customer (optional; required if the customer will collect at Pawlos), reference (free text, e.g. "ABC Furniture, phone order"), notes, **lines** (product search by code/name showing **available at Pawlos**, quantity).
- **Rules:** quantity cannot exceed what is free at Pawlos — show available next to each line and the error "Only 12 VC-001 available at PAW." Storekeepers cannot create requests.
- **After saving:** show the SR number large ("Tell the customer: SR-2026-00014") — later the SO number [P3].
- **API:** `POST /stock-requests/ {requesting_location?, source_location?, customer?, reference, notes, lines:[{product, qty}]}`.

### P-32 Stock request detail — Ready

- **Header:** SR number, transaction number, status chip, requesting branch → source, customer, reference, salesperson, created at, acknowledged by/at, closed by/at + reason.
- **Lines:** product (code + name), requested, released, **remaining**.
- **Releases:** each SRL with date, destination (To branch / Customer pickup), lines, released by, its transfer number and the transfer's status.
- **Actions by status:**

| Status | Storekeeper (source) | Requesting salesperson | Admin |
| --- | --- | --- | --- |
| Pending | Acknowledge, Reject | Cancel | all |
| Acknowledged | Release, Reject | Cancel | all |
| Partially released | Release, Close | Close | all |
| Released | Close | Close | all |
| Rejected / Cancelled / Closed | — | — | — |

- Reject, Cancel and Close need a reason. Releasing before Acknowledge is not allowed — show only the buttons that are valid.
- **API:** `GET /stock-requests/{id}/`, `POST …/acknowledge/`, `…/release/`, `…/reject/ {reason}`, `…/cancel/ {reason}`, `…/close/ {reason}`.

### P-33 Release stock — Ready (storekeeper, admin)

The storekeeper "confirms the quantity actually released". Design for a phone as well as a PC.

1. For each line: quantity to release now — defaults to the remaining quantity, with **All** and **−/+** buttons; 0 means skip the line.
2. **Destination:** **To branch** (goods go to the requesting branch; it must receive them) or **Customer pickup** (the customer collects at Pawlos; only possible when the request names a customer).
3. Optional note.
4. Summary + **Confirm** → shows the release number (SRL) and, for branch, the transfer number (TR).

- **API:** `POST /stock-requests/{id}/release/ {destination_type: "branch"|"customer_pickup", lines:[{line_id, qty}], note}`.

### P-40 New sale — P3

The most-used screen. It must be fast at the counter.

1. **Customer:** search by name/phone/shop, or **Walk-in customer** (one click), or **+ New customer** (P-62 in a side panel). Show the customer's credit status and outstanding balance.
2. **Channel:** Walk-in or Phone order.
3. **Lines:** product search by code/name → for each product show the price **for this customer** (wholesale for resellers, D11 — label it "Wholesale") and **stock at my branch and at Pawlos**. Quantity. **Source:** "From this branch" (taken now) or "From Pawlos" (creates a stock request when the sale is confirmed). Unit price comes from the product and **cannot be typed**. **Condition:** new (default), or a **display / damaged** piece from this branch's stock (D15) — usually with a discount. Discount per line (limit set by the owner in Settings, P-84; above it needs `approve_discounts`).
4. **Receipt type** ("payment type"): **Official receipt** or **Without receipt**.
5. **Payment now (optional):** amount, account (only accounts this user may use; Organization/Personal clearly marked; an official-receipt sale offers **only Organization accounts**), method, receipt number (required for official receipt + Organization — one per payment; not allowed for Personal), pay for specific lines (optional).
6. **Totals:** total, paid now, remaining (= credit).
7. **Confirm sale.** If the customer has no credit or the remaining balance is over their limit, block with a clear message unless the user has `approve_credit`. [Q11]

- **After confirm:** show the SO number large, the delivery note button (P-43), and what happens next ("15 × VC-001 requested from Pawlos — SR-…").
- **Rules:** official-receipt sales accept only Organization payments, each with its own receipt number (D3, confirmed by the owner).
- **API:** `POST /orders/ {…, payment?}`, `POST /orders/{id}/confirm/`.

### P-41 Sales / orders list — P3

- **Columns:** SO number, date, customer, branch, salesperson, channel, total, paid, remaining, fulfilment status, payment status, receipt type.
- **Scope:** salespeople see **only their own** (D9).
- **Filters:** number, status, payment status, customer, branch, salesperson, date range, receipt type.
- **API:** `GET /orders/?number=&status=&payment_status=&customer=&branch=&salesperson=&from=&to=`.

### P-42 Sale detail — P3

- **Header:** SO number, status chips, customer (link), branch, salesperson, channel, receipt type, dates; "Replaces SO-…" / "Replaced by SO-…" when voided and re-issued.
- **Lines:** product, qty, unit price, discount, line total, source, released, **held at the branch** (arrived from Pawlos, waiting for the customer), returned, **paid for this line**.
- **Totals box:** total · paid · remaining.
- **Payments:** date, PAY number, amount, **Organization/Personal**, account, status, recorded by (the client's example table). Personal amounts follow `view_personal_payments`.
- **Delivery notes and stock requests** linked to this sale.
- **History** tab = P-05.
- **Actions (by status and permission):** Edit (draft/pending only), Confirm, Record payment (P-50), **Hand over at branch** (goods held for the sale first, then free branch stock), **Request remaining stock** (after a rejected or short request), Mark prepared (storekeeper), Cancel (before any handover, reason), Return goods (P-45), **Void** (`correct_transactions`, reason), Print each delivery note.
- **API:** `GET /orders/{id}/`, `GET /orders/{id}/payments/`, `GET /orders/{id}/history/`, `POST …/confirm/`, `…/release-from-branch/ {lines:[{line_id, qty}]}`, `…/request-stock/ {lines}`, `…/status/`, `…/cancel/ {reason}`, `…/return/ {location, reason, lines}`, `…/void/ {reason}`; `PATCH /orders/{id}/` while draft/pending.

### P-43 Delivery note (print / PDF) — P3

Replaces the 3-copy paper pad (copies: storekeeper, accountant, pad).

- **Layout:** company header, **transaction (SO) number in large type**, DN number, date, customer (name, shop, phone, city), table (code, product, qty, unit price, total), payment summary (total, paid, remaining), three signature lines: salesperson, storekeeper, customer. [Q10: VAT fields; Q13: match the current paper — get a photo of it.]
- A4 portrait, black and white friendly. Also viewable on screen.
- A sale can have several delivery notes — one per handover (at the branch, or the customer's pickup at Pawlos).
- **API:** `GET /delivery-notes/?order={id}`, `GET /delivery-notes/{id}/pdf/`.

### P-44 Phone orders board — P3

For out-of-city orders (Jimma, Bahir Dar, Mekele…): **Pending → Confirmed → Prepared → Released**.

- **Board or list grouped by status** with customer, city, lines, payment status.
- Storekeeper marks **Prepared**; release happens through the stock request (customer pickup). No company delivery (D8) — never show a "Delivered/Shipping" step.
- **API:** `GET /orders/?channel=phone&status=…`, `POST /orders/{id}/status/ {"status":"prepared"}`.

### P-45 Return goods and Void sale (dialogs) — P3

- **Return goods:** pick lines and quantities (and whether each comes back **new or damaged**), the location receiving them, reason. Reduces the sale total and the customer balance. [Q7]
- **Void sale** (`correct_transactions`): for a sale entered wrongly. Shows exactly what will happen: stock goes back, the sale leaves the customer balance, its payments become the customer's credit. Reason required. Then offers **Re-issue corrected sale** (opens P-40 pre-filled, linked to the voided one).

### P-50 Record payment — P3

Opened from a sale, from a customer, or from the menu.

- **Fields:** customer, amount, account (salespeople: only their allowed accounts), method (bank / cash / mobile money), receipt number (only for Organization; required for official-receipt sales), date-time paid, note.
- **Allocation:** pay specific sales and/or specific lines ("For: 10 chairs"); the rest stays as customer credit (advance). Show each open sale's remaining and each line's remaining. Money not allocated stays the customer's advance until the accountant allocates it (owner's answer, Q20); an optional **Pay oldest first** button helps the accountant.
- **Live checks:** cannot allocate more than the payment, more than a sale's remaining or more than a line's remaining; official sale + Personal account → blocked; Personal + receipt number → blocked.
- After saving: PAY number. Salesperson payments show **Unverified** until the accountant verifies.
- **API:** `POST /payments/ {customer_id, account_id, amount, method, receipt_number?, paid_at, allocations:[{order_id, line_id?, amount}]}`.

### P-51 Payments list — P3

- **Columns:** PAY number, date, customer, amount, account, **kind (Organization/Personal)**, method, receipt number, status, recorded by, allocated to.
- **Totals bar** for the current filter: Organization · Personal · Combined.
- **Filters:** number, receipt number, account, account kind, status, customer, sale, salesperson, branch, date range.
- **Scope:** salespeople — own payments only. Personal amounts follow `view_personal_payments`.
- **API:** `GET /payments/?…`.

### P-52 Payments to verify — P3 (`verify_payments`)

- Queue of **Unverified** payments, oldest first, with who recorded them and the related sale.
- **Verify** (one click) / **Reject** (reason). Bulk verify is welcome.
- **API:** `GET /payments/?status=unverified`, `POST /payments/{id}/verify/`, `…/reject/ {reason}`.

### P-53 Payment detail — P3

- **Shows:** everything recorded + its permanent history (recorded by → amount → account → date-time → sale/customer, then each verify/reject/reverse/correct with who and why) — the "Important Permission" requirement.
- **Actions:** Verify / Reject (`verify_payments`); **Correct** (`correct_payments`: change amount, account, date or receipt number — creates a new payment and reverses the old one, linked); Reverse (`correct_payments`, reason); Allocate remaining credit (accountant/admin).
- **API:** `GET /payments/{id}/`, `POST …/verify/`, `…/reject/`, `…/reverse/`, `…/correct/`, `…/allocate/`, `…/allocate-oldest-first/`.

### P-60 Customers list — P3

- **Columns:** name, shop name, phone, city, type (Walk-in / Reseller / Out-of-city), credit allowed, credit limit, **outstanding**, total purchases.
- **Filters:** search (name, phone, shop), type, city, has balance, over limit.
- **Action:** **New customer** (salespeople can).
- **API:** `GET /customers/?search=&type=&city=`.

### P-61 Customer detail — P3

The client's example: "ABC Furniture — Total purchases 500,000 · Payments 350,000 · Outstanding 150,000".

- **Summary:** total purchases, total paid, outstanding, advance (unallocated credit), credit allowed, limit.
- **Statement:** date, document (sale or payment), debit, credit, **running balance**; each payment shows Organization/Personal. Date-range filter, print.
- **Tabs:** sales, payments, stock requests.
- **Actions:** Record payment (P-50), New sale for this customer, Edit.
- **API:** `GET /customers/{id}/`, `/balance/`, `/statement/?from=&to=`.

### P-62 Customer create / edit — P3

- **Fields:** name, phone, shop/company name, city, type, notes; **credit allowed** and **credit limit** (editable only with `approve_credit`, read-only for others).
- **Rules:** a phone number already used by another customer shows a warning, not a block (resellers may share a number).
- **API:** `POST /customers/`, `PATCH /customers/{id}/`.

### P-70 Reports — P4

Each report: filters at the top, totals, table, **Export Excel** (`export_reports`). Daily, weekly, monthly and yearly come automatically to the owner by Telegram too.

| Report | Contents | Filters |
| --- | --- | --- |
| Sales | Total sales, number of sales, paid vs credit, official vs no-receipt, by salesperson, by branch, products and quantities sold, best sellers; yearly view by month | Period (day/week/month/year or dates), branch, salesperson, customer, category |
| Payments | Organization, Personal, Combined — per day/week/month/year; payment list | Date, customer, salesperson, branch, sale, account type, account |
| Credit | Outstanding per customer with age (0–30, 31–60, 61–90, 90+ days); credit collected in the period | Date, customer, type, city |
| Stock | The P-20 matrix with low-stock flags | Location, category |
| Stock movements | Every movement with reference and person | Date, product, location, type |
| Open requests | Requests not finished, how long they've been waiting | Branch, status |
| Unverified payments | Payments waiting for the accountant | Date, salesperson |

- Salespeople see only their own sales summary; storekeepers see stock and movements. Personal figures follow `view_personal_payments`.
- **API:** `GET /reports/{sales|payments|credit|stock|movements|open-requests|unverified-payments}/?…` and `&format=xlsx` for Excel.

### P-80 Users and permissions — Ready (admin)

- **List:** name, username, role, home location, Telegram linked, active.
- **Create / edit:** username, full name, phone, role, home location (required for salesperson and storekeeper), active, password (set/reset), **permissions** (checkboxes from `GET /permissions/`, each with its label and which roles get it by default).
- **Rules:** a new user gets their role's default permissions; **changing the role resets permissions to the new role's defaults** — warn before saving. Users are deactivated, never deleted. Every change is recorded in the audit log. Admins always have every permission (show all ticked and locked). Allowed payment accounts per salesperson are added in P3.
- **API:** `GET/POST /users/`, `PATCH /users/{id}/ {…, permissions:[…]}`, `GET /permissions/`.

### P-81 Locations — Ready (admin; others read)

- **List/edit:** code, name, type (shop, warehouse, sub-store), parent, can sell, can release, active.
- **In Transit** is a system location: show it, but read-only (no edit, no deactivate).
- **API:** `GET/POST/PATCH /locations/`.

### P-82 Payment accounts — P3 (admin)

- **Fields:** name, **kind (Organization / Personal)**, method (bank / cash / mobile money), bank name, account number, owner name, active. [Q8: the real list comes from the client.]
- Which salespeople may use each account is set on the user (P-80) or here.
- The owner enters the real accounts here once the system is live (Q8).
- **API:** `GET/POST/PATCH /payment-accounts/`.

### P-84 Settings — P3 (admin)

- **Salesperson discount limit (%)** — the owner sets it (D13). Starts at 0%: every discount needs approval. Show who changed it last and when; every change goes to the audit log.
- Room for later settings (company name and address on the delivery note, etc.).
- **API:** `GET/PATCH /api/v1/settings/` [P3].

### P-83 Audit log — Ready (accountant read, admin)

"Who changed it + what was changed + date/time" for every important change.

- **Columns:** date-time, who, action (e.g. price change, user updated, adjustment approved, stock request rejected), object (type + number/name, linked), before → after (readable diff), reason, source (web / bot / system), IP.
- **Filters:** object type, object, person, action, date range.
- Read-only — no edit, no delete.
- **API:** `GET /audit/?model=&object_id=&actor=&action=&source=&from=&to=`.

---

## 6. Open points that affect the design

| Question | What may change |
| --- | --- |
| Q4, Q18 | Whether "Underground" is its own stock column; low-stock minimum per location |
| Q10, Q13 | VAT fields and layout of the delivery note (P-43) |
| Q12 | Ethiopian calendar and Amharic on screens and printouts |
| Q16 | An extra "Approved" step before the storekeeper can release (P-32) |
| Q19 | Transaction number prefix (`SO-` or the client's `PS-`) |
