# Finanzr Vue frontend

Vue 3 SPA that consumes the Django API using session cookies and CSRF
protection.

```bash
npm ci
npm run dev       # http://localhost:5173/app/
npm test
npm run build
```

With Docker, `docker compose up --build` starts PostgreSQL, Django, and Vite.
The container proxy uses `backend:8000`; outside Docker it uses `localhost:8000`.

The SPA includes the overview, savings, manual investment balances, portfolio,
real estate, funds, stocks, crypto, currencies, settings, and the supported
statement-import flows. All user-facing copy belongs in the English and Spanish
i18n catalogues under `src/i18n/`.

The isolated visual reference is available at `/app/design-preview` only while
running the Vite development server. Production builds exclude that route and
its view bundle. Current maintenance work focuses on splitting oversized views,
consolidating shared investment behavior, and keeping the frontend API types
aligned with the Django OpenAPI schema.
