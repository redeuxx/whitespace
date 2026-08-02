# Whitespace

A self-hosted pastebin built with Flask. Supports syntax highlighting, file attachments, password-protected pastes, expiry options, and an admin panel. Live demo at [https://p.wenberg.net](https://p.wenberg.net).

## Features

- Syntax highlighting with auto-language detection
- [Optional password protection with AES-256-GCM encryption at rest](https://github.com/redeuxx/whitespace/blob/main/app/utils.py#L47)
- Expiry options: burn after read, 1h, 1d, 1w, or never
- File attachments (number of attachments is configurable)
- Fork pastes to create an editable copy
- Full-text search
- Admin panel - manage pastes, ban IPs, toggle maintenance mode
- Rate-limiting options

## Deployment

- [Docker](docs/deploy-docker.md)
- [Standalone](docs/deploy-standalone.md)

## Quick start (Docker)

No clone needed - the image is published to `git.wenberg.net/redeuxx/whitespace`.

```sh
mkdir whitespace && cd whitespace/

cat > docker-compose.yml <<'EOF'
services:
  web:
    image: git.wenberg.net/redeuxx/whitespace:latest
    ports:
      - "8118:8118"
    volumes:
      - uploads_data:/app/uploads
      - db_data:/app/instance
      - ./.env:/app/.env:ro
    restart: unless-stopped

volumes:
  uploads_data:
  db_data:
EOF

# set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD
curl -o .env https://git.wenberg.net/redeuxx/whitespace/raw/branch/main/.env.example

docker compose up -d
```

App runs at [http://localhost:8118](http://localhost:8118), admin at `/admin`. This app is meant to be run behind a reverse proxy that provides SSL.

See [.env.example](.env.example) for all configuration options (file upload limits, rate limits, pagination, database URL).

## Updating (Docker)

```sh
cd whitespace/
docker compose pull
docker compose up -d
```
