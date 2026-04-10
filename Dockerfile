FROM python:3.12-slim

# Copy the uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies first (separate layer so it's cached on rebuilds)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Ensure data directories exist
RUN mkdir -p uploads instance

# flask db upgrade needs this to locate the app
ENV FLASK_APP=run.py

RUN chmod +x entrypoint.sh

EXPOSE 8118

CMD ["./entrypoint.sh"]
