#!/bin/sh
set -e

flask db upgrade

exec gunicorn --bind 0.0.0.0:8118 --workers 2 run:app
