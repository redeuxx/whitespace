import ipaddress
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, abort, current_app, flash, redirect,
    render_template, request, url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user

from ..extensions import db, login_manager
from ..models import Attachment, BannedIP, Paste, SiteSetting
from ..utils import EXPIRY_OPTIONS, time_ago, time_until

admin_bp = Blueprint('admin', __name__)


# ── Admin User (single account, credentials from .env) ────────────────────────

class AdminUser(UserMixin):
    id = 'admin'

    def get_id(self):
        return 'admin'


@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin':
        return AdminUser()
    return None


# ── IP Ban Check ──────────────────────────────────────────────────────────────

@admin_bp.before_request
def check_banned():
    ip_str = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    try:
        client = ipaddress.ip_address(ip_str)
    except ValueError:
        return
    now = datetime.utcnow()
    for ban in BannedIP.query.all():
        if ban.expires_at is not None and ban.expires_at.replace(tzinfo=None) <= now:
            db.session.delete(ban)
            db.session.commit()
            continue
        try:
            if '/' in ban.ip_address:
                if client in ipaddress.ip_network(ban.ip_address, strict=False):
                    abort(403)
            elif client == ipaddress.ip_address(ban.ip_address):
                abort(403)
        except ValueError:
            continue


# ── Context Processor ──────────────────────────────────────────────────────────

@admin_bp.context_processor
def inject_globals():
    from ..models import SiteSetting
    return {
        'site_name': SiteSetting.get('site_name', 'Whitespace'),
        'time_ago': time_ago,
        'time_until': time_until,
    }


# ── Login / Logout ─────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if (username == current_app.config['ADMIN_USERNAME'] and
                password == current_app.config['ADMIN_PASSWORD']):
            login_user(AdminUser(), remember=False)
            next_page = request.args.get('next', '')
            next_page = next_page.replace('\\', '')
            parsed = urllib.parse.urlparse(next_page)
            if not parsed.netloc and not parsed.scheme:
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials.', 'danger')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('admin.login'))


# ── Dashboard ──────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('')
@login_required
def dashboard():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_pastes = Paste.query.count()
    public_pastes = Paste.query.filter_by(is_private=False).count()
    private_pastes = Paste.query.filter_by(is_private=True).count()
    total_views = db.session.query(db.func.sum(Paste.view_count)).scalar() or 0
    pastes_today = Paste.query.filter(Paste.created_at >= today_start).count()
    expired_count = Paste.query.filter(
        Paste.expires_at.isnot(None),
        Paste.expires_at < now,
    ).count()
    banned_ips = BannedIP.query.count()
    recent_pastes = Paste.query.order_by(Paste.created_at.desc()).limit(10).all()

    return render_template(
        'admin/dashboard.html',
        total_pastes=total_pastes,
        public_pastes=public_pastes,
        private_pastes=private_pastes,
        total_views=total_views,
        pastes_today=pastes_today,
        expired_count=expired_count,
        banned_ips=banned_ips,
        recent_pastes=recent_pastes,
    )


# ── Pastes Management ──────────────────────────────────────────────────────────

@admin_bp.route('/pastes')
@login_required
def pastes():
    page = request.args.get('page', 1, type=int)
    filter_by = request.args.get('filter', 'all')
    now = datetime.now(timezone.utc)

    query = Paste.query
    if filter_by == 'public':
        query = query.filter_by(is_private=False)
    elif filter_by == 'private':
        query = query.filter_by(is_private=True)
    elif filter_by == 'expired':
        query = query.filter(Paste.expires_at.isnot(None), Paste.expires_at < now)
    elif filter_by == 'protected':
        query = query.filter(Paste.password_hash.isnot(None))

    pagination = query.order_by(Paste.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    return render_template(
        'admin/pastes.html',
        pastes=pagination.items,
        pagination=pagination,
        filter_by=filter_by,
        now=now,
    )


@admin_bp.route('/pastes/<slug>/delete', methods=['POST'])
@login_required
def delete_paste(slug):
    paste = Paste.query.filter_by(slug=slug).first_or_404()
    # Remove attachment files
    for att in paste.attachments:
        try:
            import os
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.stored_filename)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    db.session.delete(paste)
    db.session.commit()
    flash(f'Paste {slug} deleted.', 'success')
    referrer = request.referrer or ''
    # If coming from the paste's own view page it no longer exists — go home
    if f'/p/{slug}' in referrer:
        return redirect(url_for('main.index'))
    normalized_referrer = referrer.replace('\\', '')
    parsed_referrer = urllib.parse.urlparse(normalized_referrer)
    if referrer and not parsed_referrer.scheme and not parsed_referrer.netloc:
        return redirect(normalized_referrer)
    return redirect(url_for('admin.pastes'))



@admin_bp.route('/pastes/purge-expired', methods=['POST'])
@login_required
def purge_expired():
    now = datetime.now(timezone.utc)
    expired = Paste.query.filter(
        Paste.expires_at.isnot(None),
        Paste.expires_at < now,
    ).all()
    count = len(expired)
    for paste in expired:
        for att in paste.attachments:
            try:
                import os
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.stored_filename)
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        db.session.delete(paste)
    db.session.commit()
    flash(f'Purged {count} expired paste(s).', 'success')
    return redirect(url_for('admin.pastes'))


# ── IP Management ──────────────────────────────────────────────────────────────

@admin_bp.route('/ips')
@login_required
def ips():
    banned = BannedIP.query.order_by(BannedIP.banned_at.desc()).all()
    return render_template('admin/ips.html', banned=banned)


@admin_bp.route('/ips/ban', methods=['POST'])
@login_required
def ban_ip():
    ip = request.form.get('ip_address', '').strip()
    reason = request.form.get('reason', '').strip()
    expiry = request.form.get('expiry', '24h')
    if not ip:
        flash('IP address is required.', 'danger')
        return redirect(url_for('admin.ips'))

    try:
        if '/' in ip:
            ipaddress.ip_network(ip, strict=False)
        else:
            ipaddress.ip_address(ip)
    except ValueError:
        flash(f'"{ip}" is not a valid IP address or CIDR range.', 'danger')
        return redirect(url_for('admin.ips'))

    expiry_map = {
        '1h':    timedelta(hours=1),
        '6h':    timedelta(hours=6),
        '12h':   timedelta(hours=12),
        '24h':   timedelta(hours=24),
        '7d':    timedelta(days=7),
        '30d':   timedelta(days=30),
        '365d':  timedelta(days=365),
        'forever': None,
    }
    delta = expiry_map.get(expiry, timedelta(hours=24))
    expires_at = datetime.now(timezone.utc) + delta if delta is not None else None

    existing = BannedIP.query.filter_by(ip_address=ip).first()
    if existing:
        flash(f'{ip} is already banned.', 'warning')
    else:
        banned = BannedIP(ip_address=ip, reason=reason or None, expires_at=expires_at)
        db.session.add(banned)
        db.session.commit()
        flash(f'{ip} has been banned.', 'success')
    return redirect(url_for('admin.ips'))


@admin_bp.route('/ips/<int:ban_id>/unban', methods=['POST'])
@login_required
def unban_ip(ban_id):
    ban = BannedIP.query.get_or_404(ban_id)
    ip = ban.ip_address
    db.session.delete(ban)
    db.session.commit()
    flash(f'{ip} has been unbanned.', 'success')
    return redirect(url_for('admin.ips'))


# ── Site Settings ──────────────────────────────────────────────────────────────

SETTINGS_SCHEMA = [
    {
        'key': 'site_name',
        'label': 'Site Name',
        'type': 'text',
        'default': 'Whitespace',
        'help': 'The name displayed in the navbar and page title.',
    },
    {
        'key': 'site_description',
        'label': 'Site Description',
        'type': 'text',
        'default': 'A simple, clean pastebin.',
        'help': 'Short description shown in the homepage subtitle.',
    },
    {
        'key': 'public_listing_enabled',
        'label': 'Public Paste Listing',
        'type': 'toggle',
        'default': 'true',
        'help': 'Show public pastes on the homepage. Disable to hide all listings.',
    },
    {
        'key': 'maintenance_mode',
        'label': 'Maintenance Mode',
        'type': 'toggle',
        'default': 'false',
        'help': 'Show a maintenance message to all non-admin visitors.',
    },
]


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        for schema in SETTINGS_SCHEMA:
            key = schema['key']
            if schema['type'] == 'toggle':
                value = 'true' if request.form.get(key) == 'on' else 'false'
            else:
                value = request.form.get(key, schema['default']).strip()
            SiteSetting.set(key, value)
        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))

    current_settings = {
        s['key']: SiteSetting.get(s['key'], s['default'])
        for s in SETTINGS_SCHEMA
    }
    return render_template(
        'admin/settings.html',
        settings_schema=SETTINGS_SCHEMA,
        current_settings=current_settings,
        expiry_options=EXPIRY_OPTIONS,
    )


# ── About ──────────────────────────────────────────────────────────────────────

_REMOTE_PYPROJECT = (
    'https://raw.githubusercontent.com/redeuxx/whitespace/master/pyproject.toml'
)


def _fetch_latest_version():
    """Fetch the version from the upstream pyproject.toml. Returns (version, error)."""
    try:
        req = urllib.request.Request(_REMOTE_PYPROJECT, headers={'User-Agent': 'whitespace-admin'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = tomllib.loads(resp.read().decode())
        return data['project']['version'], None
    except urllib.error.URLError as e:
        return None, f'Network error: {e.reason}'
    except Exception as e:
        return None, str(e)


@admin_bp.route('/about')
@login_required
def about():
    from app import __version__
    latest_version, fetch_error = _fetch_latest_version()
    return render_template(
        'admin/about.html',
        current_version=__version__,
        latest_version=latest_version,
        fetch_error=fetch_error,
    )
