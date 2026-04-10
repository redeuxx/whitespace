# Deploying as a Standalone App

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Steps

### 1. Clone and enter the project

```sh
git clone <repo-url>
cd whitespace
```

### 2. Install dependencies

Using uv (recommended):

```sh
uv pip install --system -r requirements.txt
```

Or with a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Configure environment

```sh
cp .env.example .env
```

Edit `.env` at minimum:

```env
SECRET_KEY=<long-random-string>
FLASK_ENV=production
ADMIN_USERNAME=<your-admin-username>
ADMIN_PASSWORD=<your-admin-password>
```

Generate a secure secret key:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Create required directories

```sh
mkdir -p uploads instance
```

### 5. Run database migrations

```sh
export FLASK_APP=run.py    # Linux/macOS
set FLASK_APP=run.py       # Windows

flask db upgrade
```

### 6. Start the app

**Development** (Flask dev server, port 5000):

```sh
python run.py
```

**Production** (gunicorn, port 8118 — mirrors the Docker setup):

```sh
gunicorn --bind 0.0.0.0:8118 --workers 2 run:app
```

Change `--bind` to use a different host or port.

## Keeping it running (Linux)

Create a systemd service at `/etc/systemd/system/whitespace.service`:

```ini
[Unit]
Description=Whitespace pastebin
After=network.target

[Service]
WorkingDirectory=/path/to/whitespace
EnvironmentFile=/path/to/whitespace/.env
ExecStart=/path/to/whitespace/.venv/bin/gunicorn --bind 0.0.0.0:8118 --workers 2 run:app
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```sh
sudo systemctl daemon-reload
sudo systemctl enable whitespace
sudo systemctl start whitespace
```

## Reverse proxy (recommended for production)

Put nginx or Caddy in front of gunicorn to handle TLS and static files.

**Nginx example** (`/etc/nginx/sites-available/whitespace`):

```nginx
server {
    listen 80;
    server_name example.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8118;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Caddy example** (`Caddyfile`):

```
example.com {
    reverse_proxy 127.0.0.1:8118
}
```

## Configuration reference

All options are set via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | **Required.** Flask session signing key |
| `FLASK_ENV` | `development` | Set to `production` for production |
| `DATABASE_URL` | `sqlite:///whitespace.db` | SQLAlchemy connection string |
| `ADMIN_USERNAME` | `admin` | Admin panel username |
| `ADMIN_PASSWORD` | `changeme` | Admin panel password |
| `UPLOAD_FOLDER` | `uploads` | Path for file attachments |
| `MAX_FILE_SIZE_MB` | `10` | Max upload size per file |
| `MAX_ATTACHMENTS` | `10` | Max attachments per paste |
| `RATE_LIMIT_PASTE` | `20 per hour` | Paste creation rate limit |
| `RATE_LIMIT_SEARCH` | `60 per hour` | Search rate limit |
| `PASTES_PER_PAGE` | `20` | Pagination page size |
