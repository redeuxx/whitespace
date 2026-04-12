import base64
import html
import ipaddress
import os
import random
import re
import secrets
import socket
import string
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from werkzeug.utils import secure_filename

# Encryption format versions
_V1_PREFIX = 'enc:v1:'  # legacy: PBKDF2-SHA256 + AES-128-CBC (Fernet)
_V2_PREFIX = 'enc:v2:'  # current: Argon2id + AES-256-GCM

# Argon2id parameters — OWASP interactive profile
_ARGON2_MEMORY = 19456   # 19 MiB
_ARGON2_TIME   = 2
_ARGON2_LANES  = 1
_SALT_SIZE  = 16  # bytes
_NONCE_SIZE = 12  # bytes (96-bit GCM nonce)


def _derive_key_v2(password: str, slug: str, secret_key: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=_ARGON2_TIME,
        lanes=_ARGON2_LANES,
        memory_cost=_ARGON2_MEMORY,
        ad=slug.encode(),   # binds derived key to this paste's slug
        secret=None,
    )
    return kdf.derive((password + secret_key).encode())


def _derive_key_v1(password: str, slug: str, secret_key: str) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=slug.encode(), iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive((password + secret_key).encode()))


def encrypt_content(content: str, password: str, slug: str, secret_key: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key_v2(password, slug, secret_key, salt)
    nonce = os.urandom(_NONCE_SIZE)
    # slug passed as AAD — GCM auth fails if ciphertext is moved to a different paste
    ct = AESGCM(key).encrypt(nonce, content.encode(), slug.encode())
    blob = base64.urlsafe_b64encode(salt + nonce + ct).decode()
    return _V2_PREFIX + blob


def decrypt_content(content: str, password: str, slug: str, secret_key: str) -> str:
    if content.startswith(_V2_PREFIX):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        blob  = base64.urlsafe_b64decode(content[len(_V2_PREFIX):])
        salt  = blob[:_SALT_SIZE]
        nonce = blob[_SALT_SIZE:_SALT_SIZE + _NONCE_SIZE]
        ct    = blob[_SALT_SIZE + _NONCE_SIZE:]
        key = _derive_key_v2(password, slug, secret_key, salt)
        return AESGCM(key).decrypt(nonce, ct, slug.encode()).decode()
    if content.startswith(_V1_PREFIX):
        from cryptography.fernet import Fernet
        token = content[len(_V1_PREFIX):]
        key = _derive_key_v1(password, slug, secret_key)
        return Fernet(key).decrypt(token.encode()).decode()
    return content  # unencrypted legacy paste

from .langdetect import HLJS_LANGUAGES, PYGMENTS_TO_HLJS, detect_language  # noqa: F401

EXPIRY_OPTIONS = [
    ('burn', 'Burn after reading'),
    ('1h', '1 Hour'),
    ('1d', '1 Day'),
    ('1w', '1 Week'),
    ('never', 'Never'),
]


def generate_slug(length=8):
    from .models import Paste
    alphabet = string.ascii_letters + string.digits
    for _ in range(10):
        slug = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not Paste.query.filter_by(slug=slug).first():
            return slug
    # Fallback with longer slug
    return secrets.token_urlsafe(12)


_SINGLE_URL_RE = re.compile(r'^https?://\S+$', re.IGNORECASE)
_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)


def is_single_url(content):
    """Return True if the paste content is exactly one HTTP/HTTPS URL."""
    return bool(_SINGLE_URL_RE.match(content.strip()))


def _is_safe_url(url):
    """Return True only if the URL resolves to a public, routable IP address."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        addr = ipaddress.ip_address(socket.getaddrinfo(hostname, None)[0][4][0])
        return (
            not addr.is_private
            and not addr.is_loopback
            and not addr.is_link_local
            and not addr.is_reserved
            and not addr.is_multicast
            and not addr.is_unspecified
        )
    except (OSError, ValueError):
        return False


def fetch_url_title(url, timeout=5):
    """Fetch the <title> of a URL. Returns the title string or None on failure."""
    if not _is_safe_url(url):
        return None
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Whitespace/1.0)'})
        with urlopen(req, timeout=timeout) as resp:
            # Only read the first 32 KB — the title is always in the <head>
            chunk = resp.read(32768).decode('utf-8', errors='replace')
        m = _TITLE_RE.search(chunk)
        if m:
            return html.unescape(m.group(1).strip())[:120]
    except (URLError, OSError, ValueError):
        pass
    return None


def extract_title(content):
    """Extract a title from paste content."""
    if not content:
        return 'Untitled'
    _COMMENT_RE = re.compile(r'^(#|//|--|<!--|/\*\*?|\*)')
    candidates = [
        line.strip() for line in content.split('\n')
        if len(line.strip()) >= 30 and not _COMMENT_RE.match(line.strip())
    ]
    if not candidates:
        return 'Untitled'
    return random.choice(candidates)[:80]


def parse_expiry(expiry_str):
    """
    Returns (expires_at, burn_after_read).
    expires_at is a datetime or None (never).
    burn_after_read is a bool.
    """
    now = datetime.now(timezone.utc)
    if expiry_str == 'burn':
        return None, True
    elif expiry_str == '1h':
        return now + timedelta(hours=1), False
    elif expiry_str == '1d':
        return now + timedelta(days=1), False
    elif expiry_str == '1w':
        return now + timedelta(weeks=1), False
    else:  # 'never' or default
        return None, False


def allowed_file(filename):
    return '.' in filename and len(filename) <= 255


def save_attachment(file, upload_folder):
    """Save an uploaded file and return (original_filename, stored_filename, size)."""
    original = secure_filename(file.filename)
    ext = os.path.splitext(original)[1]
    stored = secrets.token_hex(16) + ext
    path = os.path.join(upload_folder, stored)
    file.save(path)
    size = os.path.getsize(path)
    return original, stored, size


def time_ago(dt):
    """Return a human-readable time ago string."""
    if dt is None:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        m = seconds // 60
        return f'{m} minute{"s" if m != 1 else ""} ago'
    elif seconds < 86400:
        h = seconds // 3600
        return f'{h} hour{"s" if h != 1 else ""} ago'
    elif seconds < 86400 * 30:
        d = seconds // 86400
        return f'{d} day{"s" if d != 1 else ""} ago'
    elif seconds < 86400 * 365:
        mo = seconds // (86400 * 30)
        return f'{mo} month{"s" if mo != 1 else ""} ago'
    else:
        y = seconds // (86400 * 365)
        return f'{y} year{"s" if y != 1 else ""} ago'


def time_until(dt):
    """Return a human-readable time until string for future dates."""
    if dt is None:
        return '—'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds = int((dt - now).total_seconds())
    if seconds <= 0:
        return 'expired'
    elif seconds < 3600:
        m = seconds // 60
        return f'in {m} minute{"s" if m != 1 else ""}'
    elif seconds < 86400:
        h = seconds // 3600
        return f'in {h} hour{"s" if h != 1 else ""}'
    elif seconds < 86400 * 30:
        d = seconds // 86400
        return f'in {d} day{"s" if d != 1 else ""}'
    elif seconds < 86400 * 365:
        mo = seconds // (86400 * 30)
        return f'in {mo} month{"s" if mo != 1 else ""}'
    else:
        y = seconds // (86400 * 365)
        return f'in {y} year{"s" if y != 1 else ""}'
