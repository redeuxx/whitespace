import os
import tomllib
from pathlib import Path

from flask import Flask, render_template, request

def _read_version():
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        return tomllib.load(f)["project"]["version"]

__version__ = _read_version()
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from .routes.main import main_bp
    from .routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Seed default settings (tables are created via flask db upgrade)
    with app.app_context():
        from sqlalchemy import inspect as sa_inspect
        if sa_inspect(db.engine).has_table('site_settings'):
            _seed_settings()

    # Human-friendly display names for internal highlight.js language identifiers
    _LANG_DISPLAY = {
        'x86asm': 'Assembly',
        'nasm':   'Assembly',
        'plaintext': 'Plain Text',
        'csharp': 'C#',
        'cpp':    'C++',
        'typescript': 'TypeScript',
        'javascript': 'JavaScript',
        'dockerfile': 'Dockerfile',
        'makefile': 'Makefile',
        'powershell': 'PowerShell',
    }

    @app.template_filter('lang_display')
    def lang_display_filter(lang):
        if not lang:
            return ''
        return _LANG_DISPLAY.get(lang, lang.capitalize())

    # App-level context processor so error pages get the same globals as normal pages
    @app.context_processor
    def inject_globals():
        from .models import SiteSetting
        return {
            'site_name': SiteSetting.get('site_name', 'Whitespace'),
            'site_description': SiteSetting.get('site_description', 'A simple, clean pastebin.'),
        }

    # Maintenance mode middleware
    @app.before_request
    def check_maintenance():
        from .models import SiteSetting
        if SiteSetting.get('maintenance_mode', 'false') == 'true':
            from flask_login import current_user
            if not current_user.is_authenticated:
                if not request.path.startswith('/admin'):
                    return render_template('maintenance.html'), 503

    # Custom error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(410)
    def gone(e):
        return render_template('errors/410.html'), 410

    @app.errorhandler(429)
    def too_many_requests(e):
        from .models import BannedIP, utcnow
        from .extensions import db
        from flask_limiter.util import get_remote_address
        from datetime import timedelta

        ip = get_remote_address()
        if ip:
            existing = BannedIP.query.filter_by(ip_address=ip).first()
            if not existing:
                expires_at = utcnow() + timedelta(days=1)
                ban = BannedIP(
                    ip_address=ip,
                    reason="Automatic ban: Rate limit exceeded",
                    expires_at=expires_at
                )
                db.session.add(ban)
                db.session.commit()

        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app


def _seed_settings():
    from .models import SiteSetting
    defaults = {
        'site_name': 'Whitespace',
        'site_description': 'A simple, clean pastebin.',
        'public_listing_enabled': 'true',
        'maintenance_mode': 'false',
    }
    for key, value in defaults.items():
        if SiteSetting.query.filter_by(key=key).first() is None:
            db.session.add(SiteSetting(key=key, value=value))
    db.session.commit()
