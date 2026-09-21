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
