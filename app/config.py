import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if not _env_path.exists():
    print(
        f"\nERROR: Required configuration file not found: {_env_path}\n"
        "\nThe application requires a .env file to run. "
        "Copy .env.example to .env and fill in the required values:\n"
        "\n    cp .env.example .env\n",
        file=sys.stderr,
    )
    sys.exit(1)

load_dotenv(_env_path)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///whitespace.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

    UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', 'uploads'))
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE_MB', '10')) * 1024 * 1024
    MAX_ATTACHMENTS = int(os.environ.get('MAX_ATTACHMENTS', '10'))

    RATE_LIMIT_PASTE = os.environ.get('RATE_LIMIT_PASTE', '20 per hour')
    RATE_LIMIT_SEARCH = os.environ.get('RATE_LIMIT_SEARCH', '60 per hour')

    PASTES_PER_PAGE = int(os.environ.get('PASTES_PER_PAGE', '20'))

    WTF_CSRF_ENABLED = True
