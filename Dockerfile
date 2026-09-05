FROM python:3.14-slim

# Copy the uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies first (separate layer so it's cached on rebuilds).
# uv.lock is the only source of truth; requirements.txt is no longer committed
# because Dependabot treated every pin in it as an explicitly declared
# dependency and edited it without touching the lock.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

# Copy application code
COPY . .

# Ensure data directories exist
RUN mkdir -p uploads instance

# flask db upgrade needs this to locate the app
ENV FLASK_APP=run.py

RUN chmod +x entrypoint.sh

EXPOSE 8118

CMD ["./entrypoint.sh"]
