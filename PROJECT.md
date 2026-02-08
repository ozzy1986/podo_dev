# d.onl - Domain Ownership Mining Platform

FOLLOW CURSOR RULES

## Overview

d.onl is a domain ownership mining platform built on the Waves blockchain. Users register internet domains, prove ownership via DNS TXT records, and earn DOMAIN tokens through Proof of Domain Ownership (PoDO) mining. The platform supports email/password and Waves wallet authentication, domain verification, reward distribution, SSL certificate management, domain promotions, and a public rating system.

**Core value proposition:** Users mine DOMAIN tokens by proving they own internet domains. Token rewards are distributed hourly based on a mathematical emission curve governed by a Waves smart contract.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI (Python 3.11+, async) |
| Primary DB | PostgreSQL (asyncpg) |
| Analytics DB | ClickHouse (rewards_log) |
| Blockchain | Waves (pywaves-ce, Ed25519 signatures) |
| Frontend | Vanilla JS SPA + Bootstrap 5 |
| Reverse Proxy | Nginx |
| Process Manager | systemd |
| Scheduler | APScheduler (async) |
| Auth | JWT (access + refresh tokens) + bcrypt |

## Architecture

```
Browser/Mobile App
       |
    Nginx (SSL, static files, reverse proxy)
       |
    FastAPI (uvicorn, port 8000)
       |
  +----+----+
  |         |
PostgreSQL  ClickHouse
(domains,   (rewards_log
 users,      analytics)
 promotions)
       |
    APScheduler (background jobs)
       |
    Waves Blockchain (smart contract, token distribution)
```

### Dual Database Strategy

- **PostgreSQL**: All transactional data (users, domains, promotions, subscriptions, SSL certs, payouts). Accessed via asyncpg connection pool.
- **ClickHouse**: Analytical data only (rewards_log). Optimized with monthly partitioning, TTL, materialized views for dashboard aggregations. Accessed via clickhouse-driver wrapped in asyncio.to_thread().

## Directory Structure

```
d.onl/
├── app/                    # FastAPI application (primary codebase)
│   ├── api/v1/             # API route handlers
│   │   ├── auth.py         # Auth endpoints (register, login, refresh, me)
│   │   ├── domains.py      # Domain CRUD and verification
│   │   ├── ratings.py      # Public domain/wallet ratings
│   │   ├── stats.py        # System stats and config
│   │   └── user.py         # User profile, earnings, withdrawals
│   ├── core/               # Core utilities
│   │   ├── exceptions.py   # Exception hierarchy (AppException → specific errors)
│   │   ├── middleware.py    # Logging, error handling, rate limiting, CORS
│   │   └── security.py     # JWT, bcrypt, Waves signature verification
│   ├── db/                 # Database clients
│   │   ├── clickhouse.py   # ClickHouse async wrapper
│   │   └── postgresql.py   # PostgreSQL pool manager
│   ├── models/             # Pydantic request/response models
│   ├── repositories/       # Data access layer (SQL queries)
│   ├── services/           # Business logic layer
│   ├── workers/            # Background jobs
│   │   ├── scheduler.py    # APScheduler configuration
│   │   ├── domain_processor.py   # Domain verification checks
│   │   ├── hourly_rewards.py     # Hourly reward distribution
│   │   ├── payout_scheduler.py   # Blockchain payout execution
│   │   ├── promotion_renewal.py  # Promotion subscription renewals
│   │   └── ssl_renewal.py        # SSL certificate renewal
│   ├── config.py           # Pydantic Settings (all configuration)
│   └── main.py             # FastAPI app factory and lifespan
├── config/                 # Legacy oracle configuration
├── database/               # Legacy DB modules (oracle/scripts use these)
│   ├── clickhouse.py       # Legacy ClickHouse client (oracle/scripts only)
│   ├── db_pg.py            # Legacy PG wrapper (SSL scripts only)
│   ├── migrations/         # SQL migration files (PostgreSQL + ClickHouse)
│   └── schema.sql          # Base PostgreSQL schema
├── locales/                # i18n translations (en, ru, ar)
├── oracle/                 # Blockchain oracle (separate process)
│   ├── domain_processor.py # Domain mining verification
│   ├── hourly_processor.py # Hourly reward calculations
│   ├── payout_scheduler.py # Blockchain transaction execution
│   ├── reward_processor.py # Reward amount computation
│   └── verifier.py         # DNS/WHOIS verification logic
├── scripts/                # Deployment and utility scripts
│   ├── deploy.sh           # Production deployment script
│   └── ssl/                # SSL certificate management
├── smart_contract/         # Waves smart contract (podo.ride)
├── tests/                  # Test suite (pytest)
├── tokenomics/             # Emission math (constants, weights, pool)
├── web/                    # Frontend SPA
│   ├── index.html          # Entry point
│   └── static/
│       ├── app.js          # Main orchestrator
│       ├── js/             # Modular JS files
│       │   ├── app-class.js, auth.js, dashboard.js, domains.js,
│       │   ├── ratings.js, ui.js, wallet.js, widgets.js
│       ├── api.js          # API client
│       ├── router.js       # Client-side routing
│       ├── i18n.js         # Internationalization
│       └── style.css       # Custom styles
├── .env.example            # Environment variable template
├── nginx-prod.conf         # Production nginx config
├── nginx-dev.conf          # Development nginx config
├── donl-api.service        # Production systemd service
├── dev-donl-api.service    # Development systemd service
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Poetry project metadata
└── run_tests.py            # Test runner script
```

## Core Business Logic

### Proof of Domain Ownership (PoDO)

1. **Registration**: User adds a domain name to their account.
2. **Verification**: User adds a DNS TXT record (`_mining.<domain>` or root) containing a verification token. The system verifies via multiple DNS resolvers (consensus-based).
3. **Mining**: Once verified, the domain enters the mining pool and earns DOMAIN tokens hourly.
4. **Rewards**: Hourly rewards are computed based on the domain's weight in the global pool.
5. **Payouts**: Accumulated rewards are sent to the user's Waves wallet via smart contract invocations.

### Domain Weight Calculation

Weight is determined by the Second-Level Domain (SLD) length using a Golden Ratio formula:

```
W(L) = max(1, 610 * alpha * phi^(-(L-1)))
```

Where `alpha = 6`, `phi = 1.618...` (Golden Ratio). Shorter domains have exponentially higher weights. An age bonus (up to 30%) rewards long-registered domains.

### Emission Curve

Total supply: 9,999,999,999 DOMAIN tokens. The emission follows a smooth decay:

```
E(t) = S * (1 - (1 + t/tau)^(1-alpha))
```

Where `tau ≈ 22.23 years`, `alpha = 6`. This ensures 90% of tokens are minted in ~13 years with a long tail.

### Pool Mechanics

The mining pool distributes hourly rewards proportionally to domain weights. Pool state tracks 63 buckets (one per SLD length) for efficient weight aggregation.

### Registrars, Hosters, and Domain Zones

These entities are used in ratings and as targets for comments in the social layer. They are **not** manually created; they are derived during **domain verification**:

- **Registrars**: From WHOIS at verification time. `oracle/whois_service.get_domain_whois_extra()` returns `registrar` from the WHOIS response. The app resolves it to a row in `registrars` (by name/slug) via `_get_or_create_registrar` in `database/db_pg.py`. Table: `registrars` (id, name, slug UNIQUE).
- **Hosters**: From the domain’s name servers. WHOIS returns `name_servers`; the first NS hostname is normalized by `oracle/whois_service._normalize_hoster_from_ns()` (e.g. `ns1.reg.ru` → `reg.ru`). The app resolves it to a row in `hosters` via `_get_or_create_hoster`. Table: `hosters` (id, name, slug UNIQUE).
- **Domain zones (TLD)**: Not stored in a table. Zone is derived from the domain name as the part after the last dot: `LOWER(REGEXP_REPLACE(domain, '^.*\\.', ''))` (e.g. `example.com` → `com`). Used in ratings and filtering.

So: **registrar** and **hoster** are populated when a domain is verified (WHOIS is queried and results are written to `domains.registrar_id`, `domains.hoster_id`). **Zone** is always computed from the domain string.

### Social layer (comments, votes, karma)

The platform is a "social network of domains": the main entities are **domain**, **wallet**, **registrar**, **hoster**, **zone**. Each can have a "page" with comments. Comments can have replies (threaded via `parent_id`). Anything that can be commented on can also be voted (like/dislike); votes form **karma** for that entity. **User karma** is the sum of karma of all their approved comments (each user = wallet).

- **Comments**: Stored in `comments` with `entity_type` + `entity_id` (for domain/registrar/hoster) or `entity_key` (for wallet/zone). Root comments have `parent_id = NULL`; replies have `parent_id` set. **Premoderation** is supported via `moderation_status` (`pending` | `approved` | `rejected`); by default new comments are `approved` so they pass without moderation until you switch to premoderation.
- **Votes**: One row per user per target in `votes`; `value` is +1 or -1. Targets: comment, domain, registrar, hoster, zone, wallet. Comment karma is updated automatically by a DB trigger when votes change.
- **Karma**: For comments, stored in `comments.karma_score`. For other entities, computed on read as sum of `votes.value`. User karma: sum of `karma_score` of all their approved comments.

## API Reference

All endpoints use prefix `/api/v1/`. Authentication via `Authorization: Bearer <token>` or `X-Auth-Token: <token>`.

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | No | Register with email/password |
| POST | /auth/login | No | Login with email/password |
| POST | /auth/login-wallet | No | Login with Waves wallet signature |
| POST | /auth/refresh | No | Exchange refresh token for new token pair |
| GET | /auth/me | Yes | Get current user info |

### Domains

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /domains | Yes | Add domain |
| GET | /domains | Yes | List user's domains |
| GET | /domains/{id} | Yes | Get domain details |
| DELETE | /domains/{id} | Yes | Delete domain |
| GET | /domains/{id}/verification | Yes | Get DNS TXT record to add |
| POST | /domains/{id}/verify | Yes | Verify domain ownership |
| PUT | /domains/{id}/description | Yes | Update description |
| PUT | /domains/{id}/parking | Yes | Update parking mode/content |

### Ratings (Public)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /domains/rating | No | Public domain leaderboard |
| GET | /domains/rating/wallets | No | Wallet earnings leaderboard |
| GET | /domains/rating/new | No | Recently added domains |

### User

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /user/profile | Yes | Full user profile with earnings |
| PUT | /user/language | Yes | Update language preference |
| PUT | /user/widget-preferences | Yes | Update dashboard widgets |
| GET | /user/earnings | Yes | Earnings history |
| POST | /user/withdrawal | Yes | Request token withdrawal |

### Stats

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /stats | No | System-wide statistics |
| GET | /config | No | Public app configuration |
| GET | /subscription/frequencies | No | Promotion subscription options |

### Comments and votes (social layer)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /comments | No | List root comments (query: entity_type, entity_id or entity_key) |
| GET | /comments/{id} | No | Get comment and replies |
| POST | /comments | Yes | Create comment (query: entity_type, entity_id/entity_key; body: body, parent_id?) |
| PUT | /comments/{id}/moderation | Yes | Set moderation status (premoderation) |
| DELETE | /comments/{id} | Yes | Delete own comment |
| POST | /votes | Yes | Set like/dislike (query: target_type, target_id/target_key; body: value 1 or -1) |
| DELETE | /votes | Yes | Remove vote (query: target_type, target_id/target_key) |
| GET | /karma | No | Entity karma (query: target_type, target_id/target_key) |
| GET | /user/karma | Yes | Current user karma |

### Error Response Format

All errors return a consistent envelope:

```json
{
  "ok": false,
  "error": "Human-readable message",
  "details": {},
  "status_code": 400
}
```

## Configuration

All configuration is managed via Pydantic Settings in `app/config.py`, loaded from environment variables and `.env` file. Key sections:

- **DatabaseSettings** (PG_*): PostgreSQL connection
- **ClickHouseSettings** (CH_*): ClickHouse connection
- **BlockchainSettings**: Waves node, dApp address, token config
- **SecuritySettings**: JWT secret, bcrypt rounds, rate limits, CORS
- **DNSSettings**: Resolvers, consensus, TXT record format
- **DomainSettings**: Validation rules, mining limits

Production validation enforces: strong JWT secret (32+ chars), real dApp address, non-empty PG password.

## Background Jobs

| Job | Schedule | Dev | Prod | Description |
|-----|----------|-----|------|-------------|
| Domain Processor | Every 12h | Yes | Yes | Re-verify domain DNS records |
| SSL Renewal | Daily 3am | Yes | Yes | Renew expiring certificates |
| Hourly Rewards | Every hour | No | Yes | Calculate and distribute rewards |
| Payout Processor | Every 10min | No | Yes | Execute blockchain transactions |
| Promotion Renewal | Every 15min | No | Yes | Renew promotion subscriptions |

In development mode (`APP_ENV=development`), money-related jobs are disabled.

## Security

- **JWT**: Access tokens (configurable expiry, default 30 days) + refresh tokens (60 days). Token type embedded in payload.
- **Password hashing**: bcrypt with 12 rounds.
- **Waves signature verification**: Ed25519/Curve25519 via pywaves-ce. Public key → wallet derivation verified.
- **Rate limiting**: Token bucket per IP (60 req/min general, 10 req/min for auth endpoints).
- **Production config validation**: Rejects insecure defaults at startup.
- **SQL injection prevention**: Parameterized queries throughout (PostgreSQL `$n`, ClickHouse `%(param)s`).
- **CORS**: Configurable origins (comma-separated in env).

## Database Migrations

Migrations are in `database/migrations/`. They use PostgreSQL `DO $$ BEGIN ... END $$` blocks for idempotency.

Run order: `schema.sql` first, then numbered migrations (002-019) in order, then `add_password_field.sql` and `allow_null_telegram_id.sql`. Migration `019_comments_and_votes.sql` adds `registrars`/`hosters` if missing, `comments`, `votes`, and triggers for comment karma.

ClickHouse migration: `018_clickhouse_optimized_schema.sql` (run on ClickHouse server).

## Testing

Run all tests:

```bash
python run_tests.py
```

This runs pytest with coverage and outputs:
- `logs/test_results.txt` - Full test output
- `logs/coverage_report.txt` - Coverage report

Tests mock all database calls and do not require running databases.

## Deployment

### Quick Deploy

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with production values

# 2. Run deployment
./scripts/deploy.sh

# 3. Check health
curl https://d.onl/health
```

### Manual Steps

1. Install PostgreSQL 15+, ClickHouse, Nginx, Python 3.11+
2. Create database: `createdb domain_mining`
3. Run migrations: `psql -f database/schema.sql`, then each migration file
4. Run ClickHouse migration: `clickhouse-client < database/migrations/018_clickhouse_optimized_schema.sql`
5. Setup venv: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
6. Configure `.env` (see `.env.example`)
7. Install nginx config: copy `nginx-prod.conf` to `/etc/nginx/sites-available/d.onl`
8. Install systemd service: copy `donl-api.service` to `/etc/systemd/system/`
9. Start: `sudo systemctl start donl-api`

### Rollback

```bash
./scripts/deploy.sh --rollback
```

## Mobile App Integration

The API is designed for future Android/iOS apps:

- JWT refresh tokens for seamless re-authentication
- Consistent JSON error envelope (`ok`, `error`, `details`, `status_code`)
- OpenAPI docs always available at `/api/docs` and `/api/redoc`
- CORS configurable for mobile origins
- All endpoints return JSON, no HTML rendering server-side

## ClickHouse Optimization

The `rewards_log` table uses:
- **MergeTree engine** with monthly partitioning (`PARTITION BY toYYYYMM(created_at)`)
- **ORDER BY (wallet, created_at)** matching primary query patterns
- **TTL 730 days** for automatic data retention
- **LowCardinality(String)** for status column
- **ZSTD(3) compression** across all columns
- **Materialized views**: `rewards_daily_stats` (per-wallet daily totals) and `rewards_domain_totals` (per-domain totals)

Expected data volume: 1,000-10,000 domains, manageable with these optimizations.
