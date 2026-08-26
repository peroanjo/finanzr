# Demo User and Data

Finanzr provides a demonstration workspace isolated from all other users.
All amounts, movements, and names are synthetic.

## Local access

- Email: `demo@finanzr.local`
- Password: `finanzr-demo-local`
- Workspace: `Demo Finanzr`

The user has the `owner` role only inside the `demo` workspace.

## Contents

The dataset covers twelve monthly closes and includes:

- Three savings accounts, one of them interest-bearing.
- Three manual investment balances.
- Four funds and eight subscriptions.
- Four stock and ETF positions.
- Bitcoin and Ethereum with several purchases.
- One active and one completed real-estate project.
- One manual alternative investment.

Market-instrument identifiers are public so that price queries can work.
Quantities, purchase dates, balances, contributions, and returns are fictitious.

## Regeneration

```bash
docker compose exec backend python manage.py seed_demo_data
```

The command is idempotent: it deletes and rebuilds only the workspace with the
`demo` slug. It does not modify other users or workspaces. Alternative
credentials can be supplied:

```bash
docker compose exec backend python manage.py seed_demo_data \
  --email demo@example.test \
  --password 'UnaClaveDemoSegura'
```

The account uses a known password and should not be retained in a production
installation exposed to the Internet unless it is needed.
