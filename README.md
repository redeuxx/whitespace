# Whitespace

A self-hosted pastebin built with Flask. Supports syntax highlighting, file attachments, password-protected pastes, expiry options, and an admin panel. Live demo at [https://p.wenberg.net](https://p.wenberg.net).

## Features

- Syntax highlighting with auto-language detection
- [Optional password protection with AES-256-GCM encryption at rest](https://github.com/redeuxx/whitespace/blob/main/app/utils.py#L47)
- Expiry options: burn after read, 1h, 1d, 1w, or never
- File attachments (number of attachments is configurable)
- Full-text search
- Admin panel — manage pastes, ban IPs, toggle maintenance mode
- Rate-limiting options

## Deployment

- [Docker](docs/deploy-docker.md)
- [Standalone](docs/deploy-standalone.md)

## Quick start (Docker)

```sh
git clone https://github.com/redeuxx/whitespace.git
cd whitespace/
# set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD
cp .env.example .env   
docker compose up --build -d
```

App runs at [http://localhost:8118](http://localhost:8118), admin at `/admin`.

## Updating (Docker)

```sh
cd whitespace/
git pull 
docker compose up --build -d
```
