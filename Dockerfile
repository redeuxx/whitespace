FROM python:3.14-alpine

# Pull OS security fixes released after the base image was built.
RUN apk upgrade --no-cache

WORKDIR /app

# Install dependencies first (separate layer so it's cached on rebuilds).
# uv.lock is the only source of truth; requirements.txt is no longer committed
# because Dependabot treated every pin in it as an explicitly declared
# dependency and edited it without touching the lock.
#
# uv is mounted from Astral's image only for this step, so it never ships.
# It syncs the lock straight into the system Python. pip is removed: nothing
# uses it at runtime, and its vendored urllib3, msgpack and setuptools carry
# CVEs that scanners flag. uv sync leaves pip alone, so uninstall it here.
# Bytecode is compiled at build time: the runtime user cannot write .pyc
# files, so without this every start recompiles everything in memory.
ENV UV_PROJECT_ENVIRONMENT=/usr/local UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.6,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev --no-install-project --no-cache \
 && python -m pip uninstall -y -q pip

# Copy application code
COPY . .

# Run as an unprivileged user that owns only the data directories. New named
# volumes inherit this ownership; volumes created by older root images need a
# one-time chown (see docs/deploy-docker.md).
RUN python -m compileall -q app  && adduser -D -u 1000 app \
 && mkdir -p uploads instance \
 && chown app:app uploads instance

# flask db upgrade needs this to locate the app
ENV FLASK_APP=run.py

RUN chmod +x entrypoint.sh

USER app

EXPOSE 8118

CMD ["./entrypoint.sh"]
