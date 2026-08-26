# Finanzr Vue frontend

Vue 3 SPA that consumes the Django API using session cookies and CSRF
protection.

```bash
npm install
npm run dev       # http://localhost:5173/app/
npm test
npm run build
```

With Docker, `docker compose up --build` starts PostgreSQL, Django, and Vite.
The container proxy uses `backend:8000`; outside Docker it uses `localhost:8000`.

The financial sections, overview, net-worth chart, and three importers are
available. Additional editing flows are being implemented progressively.

The final design is being applied section by section. `Overview` already uses
the modern shell, light/dark themes, and real data from `/api/summary` and
`/api/net-worth-history`. The isolated visual reference remains available at
`/app/design-preview`; the remaining sections will be implemented progressively.
