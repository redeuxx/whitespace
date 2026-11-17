# Deploying with Docker

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed (included with Docker Desktop)

## Steps

### 1. Clone the repo

```sh
git clone https://github.com/redeuxx/whitespace.git
cd whitespace/
```

The repo ships a `docker-compose.yml` with the port, volumes and `.env` mount
already wired up, so there is nothing to write by hand.

### 2. Configure environment

```sh
cp .env.example .env
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

### 3. Build and start

```sh
docker compose up -d --build
```

This will:
- Build the image from the checkout
- Run database migrations automatically
- Start gunicorn on port **8118** (one worker, four threads)
- Persist uploads and the SQLite database in named Docker volumes

### 4. Access the app

Open [http://localhost:8118](http://localhost:8118) in your browser.

The admin panel is at [http://localhost:8118/admin](http://localhost:8118/admin).

## Managing the container

| Task | Command |
|------|---------|
| View logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Deploy a new build | `git pull && docker compose build --pull --no-cache && docker compose up -d` |
| Roll back to a known commit | `git checkout <sha>` then `docker compose up -d --build` |

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

### Upgrading from a root image

The container runs as user `app` (uid 1000). Volumes created by older images
that ran as root are owned by root, so the app cannot write to them. Fix the
ownership once, then rebuild:

```sh
docker compose build
docker compose down
docker compose run --rm --user root --entrypoint chown web -R app:app /app/uploads /app/instance
docker compose up -d
```

## Changing the port

The app listens on **8118** internally (set in `entrypoint.sh`). To use a different host port, edit `docker-compose.yml`:

```yaml
ports:
  - "127.0.0.1:9000:8118"   # host:container
```

Keep the `127.0.0.1:` prefix. The app takes the client IP from the last `X-Forwarded-For` entry, which only a reverse proxy should set. Your proxy must add or overwrite that header (nginx: `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`). Without it, clients can fake their IP and get around bans and rate limits.

## Using a production database

Set `DATABASE_URL` in `.env` to a PostgreSQL or MySQL connection string:

```env
DATABASE_URL=postgresql://user:password@host:5432/whitespace
```

Add the database service to `docker-compose.yml` or point to an external host.
