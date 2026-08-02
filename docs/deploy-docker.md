# Deploying with Docker

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed (included with Docker Desktop)

## Steps

The image is published to `git.wenberg.net/redeuxx/whitespace`, so a deployment
host only needs a `docker-compose.yml` and a `.env` - no clone, no source
checkout.

### 1. Create the compose file

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
```

### 2. Configure environment

Grab the example env file and fill in your values:

```sh
curl -o .env https://git.wenberg.net/redeuxx/whitespace/raw/branch/main/.env.example
```

Edit `.env` at minimum:

```env
SECRET_KEY=<long-random-string>
ADMIN_USERNAME=<your-admin-username>
ADMIN_PASSWORD=<your-admin-password>
```

Generate a secure secret key if needed:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Pull and start

```sh
docker compose pull
docker compose up -d
```

This will:
- Pull the prebuilt image from `git.wenberg.net/redeuxx/whitespace:latest`
- Run database migrations automatically
- Start gunicorn on port **8118** with 2 workers
- Persist uploads and the SQLite database in named Docker volumes

The image is built by the `Build and publish image` workflow on every push to
`main`, so the deployment host never compiles anything. To build from source
instead (development, or an unpushed change), clone the repo and use its
`docker-compose.yml`, which keeps a `build:` section:

```sh
git clone https://git.wenberg.net/redeuxx/whitespace.git
cd whitespace/
docker compose up --build -d
```

### 4. Access the app

Open [http://localhost:8118](http://localhost:8118) in your browser.

The admin panel is at [http://localhost:8118/admin](http://localhost:8118/admin).

## Managing the container

| Task | Command |
|------|---------|
| View logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Deploy a new build | `docker compose pull && docker compose up -d` |
| Rebuild from a source checkout | `docker compose up -d --build` |
| Roll back to a known commit | `docker compose up -d` with `image:` pinned to `git.wenberg.net/redeuxx/whitespace:<12-char-sha>` |

## Data persistence

Two named volumes keep your data across container restarts and rebuilds:

| Volume | Contents |
|--------|----------|
| `uploads_data` | Uploaded file attachments |
| `db_data` | SQLite database (`instance/whitespace.db`) |

To back up the database:

```sh
docker compose cp web:/app/instance/whitespace.db ./whitespace.db.bak
```

## Changing the port

The app listens on **8118** internally (set in `entrypoint.sh`). To expose it on a different host port, edit `docker-compose.yml`:

```yaml
ports:
  - "9000:8118"   # host:container
```

## Using a production database

Set `DATABASE_URL` in `.env` to a PostgreSQL or MySQL connection string:

```env
DATABASE_URL=postgresql://user:password@host:5432/whitespace
```

Add the database service to `docker-compose.yml` or point to an external host.
