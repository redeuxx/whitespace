FROM python:3.14-alpine

# Pull OS security fixes released after the base image was built.
RUN apk upgrade --no-cache

WORKDIR /app

# Install dependencies first (separate layer so it's cached on rebuilds).
# uv.lock is the only source of truth; requirements.txt is no longer committed
# because Dependabot treated every pin in it as an explicitly declared
# dependency and edited it without touching the lock.
#
# Do not give this project a [build-system]. It makes uv treat the root as
# installable rather than virtual, so uv export tries to build it here and
# fails with "package directory 'app' does not exist" - only pyproject.toml
# and uv.lock are copied at this point, deliberately, to keep the layer
# cached across application changes.
#
# uv is mounted from Astral's image only for this step, so it never ships.
# pip is removed: nothing uses it at runtime, and its vendored urllib3,
# msgpack and setuptools carry CVEs that scanners flag.
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/bin/uv \
    uv export --frozen --no-dev --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt \
 && python -m pip uninstall -y -q pip

# Copy application code
COPY . .

# Run as an unprivileged user that owns only the data directories. New named
# volumes inherit this ownership; volumes created by older root images need a
# one-time chown (see docs/deploy-docker.md).
RUN adduser -D -u 1000 app \
 && mkdir -p uploads instance \
 && chown app:app uploads instance

# flask db upgrade needs this to locate the app
ENV FLASK_APP=run.py

RUN chmod +x entrypoint.sh

USER app

EXPOSE 8118

CMD ["./entrypoint.sh"]
