# Python runtime

This project uses Python 3.13.15 and Django 5.2.17 LTS.

On this Mac, activate the prepared environment from the project folder:

```sh
source .venv/bin/activate
python3 --version
python3 -m django --version
```

In VS Code, select `.venv/bin/python` using **Python: Select Interpreter**.
Restart any development server after activating the environment.

For a fresh checkout, install Python 3.13.15, then run:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 manage.py check
python3 manage.py test
```

The `.python-runtime` directory contains the isolated Python installation prepared
on this Mac. Keep it while using this `.venv`; neither directory belongs in Git.
The temporary uv installation used to obtain Python is not an application dependency.
Database migrations and deployment configuration are separate steps.

## Environment settings

Settings load `.env` from the project root without overriding process environment
variables. A private development `.env` has been created on this Mac with a new
secret and `DJANGO_DEBUG=True`. Do not commit it.

On a fresh checkout, copy `.env.example` to `.env`, supply a newly generated
`DJANGO_SECRET_KEY`, and set `DJANGO_DEBUG=True` only for local development.
`DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` accept comma-separated
values. CSRF origins include the scheme (for example, `https://example.com`).
Set `DJANGO_READ_DOTENV=False` in the process environment when all settings
should come from the deployment environment. A missing or empty secret prevents
startup; debug defaults to false when not explicitly enabled.

## Database selection

An unset or empty `DATABASE_URL` keeps `BASE_DIR / "db.sqlite3"` unchanged.
Set a private `DATABASE_URL` to use PostgreSQL without changing source code:

```text
postgresql://DB_USER:DB_PASSWORD@DB_HOST:5432/DB_NAME?sslmode=require
```

These are placeholders, not credentials. Percent-encode reserved characters in
usernames/passwords. Use the database service's required SSL mode and certificate
settings; `sslmode=verify-full` requires a trusted CA and matching hostname.
Process environment values take precedence over `.env`. Invalid/non-PostgreSQL
URLs fail configuration rather than silently falling back to SQLite.

The driver is Psycopg 3 with its matching binary distribution. Connections use
Django's default per-request lifetime (`CONN_MAX_AGE=0`); pooling is not configured.
No PostgreSQL server has been provisioned, no migrations have been applied to one,
and no SQLite records have been transferred. Production must explicitly supply
`DATABASE_URL`; do not deploy with the SQLite fallback unintentionally.

When a PostgreSQL server is available, verify connectivity, apply the existing
migrations to the intended new database, and run tests against a separate test
database (with appropriate create-database permission). Test simultaneous bookings
for the same slot and repeated intro orders. Current local tests run on SQLite,
which does not enforce `select_for_update()` row locks. Public/admin booking locks
select individual tables without nullable outer joins. Database constraints remain
unchanged. Keep real production credentials out of test commands and logs.

## Production static files and WSGI

Build CSS before collecting assets, using the project's activated virtual environment:

```sh
npm ci
npm run build:css -- --minify
python manage.py collectstatic --noinput
```

WhiteNoise runs immediately after SecurityMiddleware. Source files remain in
`website/static/website/`; `STATIC_URL` is unchanged. Collection includes Django
Admin assets and generates hashed/compressed assets plus a manifest in `staticfiles/`.
This generated directory is ignored by Git and must be included in the deployed
runtime filesystem. Rebuild and recollect after changing source assets.

With production environment variables supplied, start the server using:

```sh
.venv/bin/gunicorn highlegh.wsgi:application --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
```

Use the hosting environment's assigned port instead of 8000 when required. Worker
count, timeouts, process supervision, health checks, reverse proxy configuration,
and HTTPS remain deployment-specific. Stop Gunicorn gracefully with SIGTERM.

Local development is unchanged: activate `.venv` and run `python manage.py runserver`.
With local DEBUG=True, Django continues serving source static files through runserver.
For DEBUG=False, run collectstatic before starting the application.

## HTTPS and security policy

`DJANGO_DEBUG=False` enables secure session/CSRF cookies and HTTP-to-HTTPS
redirects. Local `DJANGO_DEBUG=True` disables those three settings and HSTS so
HTTP runserver remains usable. Explicit headers protect against MIME sniffing,
framing, cross-origin opener access and cross-origin referrer disclosure.
Session cookies remain HttpOnly; session/CSRF cookies use SameSite=Lax.

Before launch configure the actual allowed hosts and required trusted HTTPS
origins. If TLS terminates at a reverse proxy, enable
`DJANGO_TRUST_PROXY_SSL_HEADER=True` ONLY when the proxy strips incoming
X-Forwarded-Proto and supplies its own value, and direct public access to Gunicorn
is blocked. This flag trusts that header; Django does not verify the sender's IP.
Without those guarantees leave it False. Forwarded host and port are not trusted.
Verify redirects do not loop and HTTPS forms/login work through the final proxy.

HSTS defaults to zero, with subdomains and preload disabled. After validating
certificates, HTTPS and redirects, set `DJANGO_SECURE_HSTS_SECONDS=300` for a short
trial. Increase deliberately after monitoring. Do not enable subdomains or preload
without a separate review of every affected hostname. The deployment check's
missing-HSTS warning is expected while this rollout is deferred.

For local production-mode testing, supply an actual HTTPS listener or use Django's
test client with secure=True. Plain HTTP production requests redirect by design.
