# Furniture ERP — Web app

React web app for the Furniture ERP: every page in `../UI_PAGES.md` (P-01 to P-84), built to the
"Furniture ERP UI" design, talking to the Django API in `../backend`.

**Stack:** React 19 · TypeScript · Vite · React Router · TanStack Query · plain CSS (design tokens in
`src/styles/app.css`) · Vitest

## Run it

The API must be running first (`docker compose up -d` in `../backend`, then
`docker compose exec api python manage.py seed_demo` for demo users).

```bash
npm install
npm run dev          # http://localhost:5173 — /api is forwarded to http://localhost:8000
```

Log in with a demo user (password `Demo-pass-2026`): `admin`, `accountant`, `sales_pia` (Piassa),
`sales_den` (Denbel), `store_paw` (Pawlos). Each role sees its own menu and home page.

To point the dev server at another API: `VITE_API_PROXY=http://host:8000 npm run dev`.

## Checks

```bash
npm run typecheck    # TypeScript, strict
npm run lint         # oxlint
npm test             # Vitest (Ethiopian calendar, …)
npm run build        # production build into dist/
npm run gen:api      # regenerate src/api/schema.d.ts from the running API's OpenAPI schema
```

## Layout

```
src/
  api/          client.ts (tokens, silent refresh, errors), hooks.ts (queries, actions),
                types.ts, schema.d.ts (generated from the API)
  auth/         AuthContext — login, /auth/me/, can(permission), is(role)
  components/   Layout (sidebar per role, top bar), ui (chips, money, dates, fields, pager),
                Dialog (confirm / reason), pickers (product, customer), EthDatePicker,
                PeriodPicker, LinesEditor, inputs (money, quantity stepper, search)
  lib/          ethiopian.ts (port of backend/apps/core/ethiopian.py), format, labels, nav
                (menus per role), useFilters (list filters kept in the URL)
  pages/        one file per page, grouped like UI_PAGES.md section 6
```

## Rules the pages follow (UI_PAGES.md section 3)

- **Money** is shown as the API sends it; no money arithmetic except previews the server recomputes.
- **Dates** are Ethiopian first, Gregorian beside them, Addis Ababa time (D16).
- **Sensitive buttons are hidden, not disabled**, when the user lacks the permission; the API still
  checks everything.
- **Every action that changes stock or money asks first**, restating what will happen; reject,
  cancel, close, void, reverse and correct always need a reason.
- **No delete, no typed prices, no direct stock edits** anywhere.

## Production

`npm run build` writes static files to `dist/`. Serve them with nginx on the same domain as the
API, sending `/api/` to Django and every other path to `index.html` (client-side routing).
