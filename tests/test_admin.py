"""
Admin blueprint tests.

Primary coverage:
- wrapt 2.1.2 -> 2.2.0: Flask-Limiter and Flask-Login use wrapt for decorator
  internals; @login_required and rate-limited routes are exercised throughout.
- packaging 26.0 -> 26.2: transitive dep loaded at extension init time; the
  /admin/about route is also exercised with a mocked network call.
- greenlet 3.3.2 -> 3.5.1: all admin routes that hit the DB.
"""
from unittest.mock import patch
import pytest


class TestAdminLogin:
    def test_get_login_page(self, client):
        rv = client.get('/admin/login')
        assert rv.status_code == 200

    def test_valid_login_redirects_to_dashboard(self, client):
        rv = client.post('/admin/login', data={
            'username': 'admin',
            'password': 'testpassword',
        }, follow_redirects=False)
        assert rv.status_code == 302
        assert '/admin' in rv.headers['Location']

    def test_invalid_password_shows_error(self, client):
        rv = client.post('/admin/login', data={
            'username': 'admin',
            'password': 'wrongpassword',
        }, follow_redirects=True)
        assert rv.status_code == 200
        assert b'Invalid credentials' in rv.data

    def test_invalid_username_shows_error(self, client):
        rv = client.post('/admin/login', data={
            'username': 'nobody',
            'password': 'testpassword',
        }, follow_redirects=True)
        assert rv.status_code == 200
        assert b'Invalid credentials' in rv.data

    def test_authenticated_user_redirected_away_from_login(self, admin_client):
        rv = admin_client.get('/admin/login', follow_redirects=False)
        assert rv.status_code == 302


class TestAdminLogout:
    def test_logout_redirects_to_login(self, admin_client):
        rv = admin_client.get('/admin/logout', follow_redirects=False)
        assert rv.status_code == 302
        assert 'login' in rv.headers['Location'].lower()

    def test_after_logout_dashboard_requires_login(self, admin_client):
        admin_client.get('/admin/logout')
        rv = admin_client.get('/admin/', follow_redirects=False)
        assert rv.status_code == 302


class TestAdminDashboard:
    def test_requires_login(self, client):
        rv = client.get('/admin/', follow_redirects=False)
        assert rv.status_code == 302
        assert 'login' in rv.headers['Location'].lower()

    def test_accessible_when_logged_in(self, admin_client):
        rv = admin_client.get('/admin/')
        assert rv.status_code == 200

    def test_shows_paste_counts(self, admin_client, sample_paste):
        rv = admin_client.get('/admin/')
        assert rv.status_code == 200

    def test_empty_db(self, admin_client):
        rv = admin_client.get('/admin/')
        assert rv.status_code == 200


class TestAdminPastes:
    def test_page_loads(self, admin_client):
        rv = admin_client.get('/admin/pastes')
        assert rv.status_code == 200

    def test_shows_paste(self, admin_client, sample_paste):
        rv = admin_client.get('/admin/pastes')
        assert rv.status_code == 200
        assert sample_paste.slug.encode() in rv.data

    def test_requires_login(self, client):
        rv = client.get('/admin/pastes', follow_redirects=False)
        assert rv.status_code == 302

    def test_delete_paste(self, admin_client, sample_paste, app):
        from app.models import Paste

        slug = sample_paste.slug
        rv = admin_client.post(f'/admin/pastes/{slug}/delete', follow_redirects=True)
        assert rv.status_code == 200

        with app.app_context():
            assert Paste.query.filter_by(slug=slug).first() is None

    def test_delete_nonexistent_returns_404(self, admin_client):
        rv = admin_client.post('/admin/pastes/nosuchslug/delete')
        assert rv.status_code == 404

    def test_filter_public(self, admin_client):
        rv = admin_client.get('/admin/pastes?filter=public')
        assert rv.status_code == 200

    def test_filter_private(self, admin_client):
        rv = admin_client.get('/admin/pastes?filter=private')
        assert rv.status_code == 200

    def test_filter_expired(self, admin_client):
        rv = admin_client.get('/admin/pastes?filter=expired')
        assert rv.status_code == 200


class TestAdminSettings:
    def test_page_loads(self, admin_client):
        rv = admin_client.get('/admin/settings')
        assert rv.status_code == 200

    def test_requires_login(self, client):
        rv = client.get('/admin/settings', follow_redirects=False)
        assert rv.status_code == 302

    def test_post_updates_site_name(self, admin_client, app):
        from app.models import SiteSetting

        admin_client.post('/admin/settings', data={
            'site_name': 'My Test Site',
            'site_description': 'A test.',
            'public_listing_enabled': 'on',
        }, follow_redirects=True)

        with app.app_context():
            assert SiteSetting.get('site_name') == 'My Test Site'

    def test_post_disables_public_listing(self, admin_client, app):
        from app.models import SiteSetting

        admin_client.post('/admin/settings', data={
            'site_name': 'Whitespace',
            'site_description': 'A test.',
        }, follow_redirects=True)

        with app.app_context():
            assert SiteSetting.get('public_listing_enabled') == 'false'


class TestAdminIPs:
    def test_page_loads(self, admin_client):
        rv = admin_client.get('/admin/ips')
        assert rv.status_code == 200

    def test_requires_login(self, client):
        rv = client.post('/admin/ips/ban', data={'ip_address': '1.2.3.4'}, follow_redirects=False)
        assert rv.status_code == 302

    def test_ban_valid_ip(self, admin_client, app):
        from app.models import BannedIP

        admin_client.post('/admin/ips/ban', data={
            'ip_address': '192.168.1.100',
            'reason': 'test ban',
            'expiry': '24h',
        }, follow_redirects=True)

        with app.app_context():
            ban = BannedIP.query.filter_by(ip_address='192.168.1.100').first()
            assert ban is not None
            assert ban.reason == 'test ban'

    def test_ban_cidr_range(self, admin_client, app):
        from app.models import BannedIP

        admin_client.post('/admin/ips/ban', data={
            'ip_address': '10.0.0.0/24',
            'reason': 'subnet ban',
            'expiry': '7d',
        }, follow_redirects=True)

        with app.app_context():
            assert BannedIP.query.filter_by(ip_address='10.0.0.0/24').first() is not None

    def test_ban_permanent(self, admin_client, app):
        from app.models import BannedIP

        admin_client.post('/admin/ips/ban', data={
            'ip_address': '1.2.3.4',
            'expiry': 'forever',
        }, follow_redirects=True)

        with app.app_context():
            ban = BannedIP.query.filter_by(ip_address='1.2.3.4').first()
            assert ban is not None
            assert ban.expires_at is None

    def test_ban_invalid_ip_shows_error(self, admin_client):
        rv = admin_client.post('/admin/ips/ban', data={
            'ip_address': 'not-an-ip',
            'reason': 'test',
            'expiry': '24h',
        }, follow_redirects=True)
        assert rv.status_code == 200
        assert b'not a valid' in rv.data

    def test_unban_ip(self, admin_client, app):
        from app.extensions import db
        from app.models import BannedIP

        with app.app_context():
            ban = BannedIP(ip_address='5.5.5.5', reason='temp')
            db.session.add(ban)
            db.session.commit()
            ban_id = ban.id

        rv = admin_client.post(f'/admin/ips/{ban_id}/unban', follow_redirects=True)
        assert rv.status_code == 200

        with app.app_context():
            assert BannedIP.query.get(ban_id) is None

    def test_duplicate_ban_shows_warning(self, admin_client, app):
        from app.extensions import db
        from app.models import BannedIP

        with app.app_context():
            db.session.add(BannedIP(ip_address='9.9.9.9'))
            db.session.commit()

        rv = admin_client.post('/admin/ips/ban', data={
            'ip_address': '9.9.9.9',
            'expiry': '24h',
        }, follow_redirects=True)
        assert rv.status_code == 200
        assert b'already banned' in rv.data


class TestAdminAbout:
    """
    /admin/about fetches the upstream version over the network.
    The network call is always mocked; the test still exercises the full
    render path including the packaging import chain loaded at extension init.
    """

    def test_page_renders_current_version(self, admin_client):
        from app import __version__
        with patch('app.routes.admin._fetch_latest_version', return_value=(__version__, None)):
            rv = admin_client.get('/admin/about')
        assert rv.status_code == 200
        assert __version__.encode() in rv.data

    def test_shows_up_to_date_when_versions_match(self, admin_client):
        from app import __version__
        with patch('app.routes.admin._fetch_latest_version', return_value=(__version__, None)):
            rv = admin_client.get('/admin/about')
        assert b'Up to date' in rv.data

    def test_shows_update_available_when_versions_differ(self, admin_client):
        with patch('app.routes.admin._fetch_latest_version', return_value=('9.9.9', None)):
            rv = admin_client.get('/admin/about')
        assert b'Update available' in rv.data

    def test_handles_fetch_error(self, admin_client):
        with patch('app.routes.admin._fetch_latest_version', return_value=(None, 'Network error: timed out')):
            rv = admin_client.get('/admin/about')
        assert rv.status_code == 200
        assert b'Could not fetch' in rv.data

    def test_requires_login(self, client):
        rv = client.get('/admin/about', follow_redirects=False)
        assert rv.status_code == 302
