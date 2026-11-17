#!/bin/sh
set -e

for dir in /app/instance /app/uploads; do
    if [ ! -w "$dir" ]; then
        echo "error: $dir is not writable by $(id -un) (uid $(id -u))." >&2
        echo "Volumes created by images before v1.0.5 are owned by root and need a one-time chown." >&2
        echo "See 'Upgrading from a root image' in docs/deploy-docker.md." >&2
        exit 1
    fi
done

flask db upgrade

exec gunicorn --bind 0.0.0.0:8118 --workers 2 run:app
