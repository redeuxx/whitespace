"""
Main blueprint route tests.

Primary coverage:
- wrapt 2.1.2 -> 2.2.0: Flask-Limiter uses wrapt for decorator internals; all
  rate-decorated routes are exercised here.
- greenlet 3.3.2 -> 3.5.1: every request that touches the DB.
"""
from datetime import datetime, timedelta, timezone
import pytest


class TestIndexRoute:
    def test_get_returns_200(self, client):
        rv = client.get('/')
        assert rv.status_code == 200

    def test_shows_public_paste(self, client, sample_paste):
        rv = client.get('/')
        assert rv.status_code == 200
        assert b'Test Paste' in rv.data

    def test_private_paste_excluded(self, client, private_paste):
        rv = client.get('/')
        assert b'Private Paste' not in rv.data

    def test_pagination_param_accepted(self, client):
        rv = client.get('/?page=1')
        assert rv.status_code == 200


class TestNewPasteRoute:
    def test_get_returns_form(self, client):
        rv = client.get('/new')
        assert rv.status_code == 200
        assert b'<form' in rv.data

    def test_post_creates_paste_and_redirects(self, client):
        rv = client.post('/new', data={'content': 'My new paste content here'}, follow_redirects=False)
        assert rv.status_code == 302
        assert '/p/' in rv.headers['Location']

    def test_post_empty_content_returns_error(self, client):
        rv = client.post('/new', data={'content': ''}, follow_redirects=True)
        assert rv.status_code == 200
        assert b'cannot be empty' in rv.data

    def test_post_with_title(self, client):
        rv = client.post('/new', data={
            'content': 'Some content for a titled paste',
            'title': 'My Title',
        }, follow_redirects=True)
        assert rv.status_code == 200
        assert b'My Title' in rv.data

    def test_post_private_paste(self, client):
        rv = client.post('/new', data={
            'content': 'This is private content',
            'visibility': 'private',
        }, follow_redirects=True)
        assert rv.status_code == 200

    def test_post_with_expiry_1h(self, client):
        rv = client.post('/new', data={
            'content': 'Expires in an hour',
            'expiry': '1h',
        }, follow_redirects=True)
        assert rv.status_code == 200

    def test_post_burn_after_read_creates_paste(self, client):
        rv = client.post('/new', data={
            'content': 'Burn this after reading',
            'expiry': 'burn',
        }, follow_redirects=False)
        assert rv.status_code == 302
        assert '/p/' in rv.headers['Location']

    def test_post_with_language(self, client):
        rv = client.post('/new', data={
            'content': 'def foo(): pass',
            'language': 'python',
        }, follow_redirects=True)
        assert rv.status_code == 200


class TestViewPasteRoute:
    def test_get_existing_paste(self, client, sample_paste):
        rv = client.get(f'/p/{sample_paste.slug}')
        assert rv.status_code == 200
        assert b'Hello, world!' in rv.data

    def test_get_nonexistent_returns_404(self, client):
        rv = client.get('/p/doesnotexist')
        assert rv.status_code == 404

    def test_view_increments_view_count(self, client, sample_paste, app):
        from app.models import Paste

        client.get(f'/p/{sample_paste.slug}')
        with app.app_context():
            updated = Paste.query.filter_by(slug=sample_paste.slug).first()
            assert updated.view_count == 1

    def test_private_paste_accessible_by_direct_link(self, client, private_paste):
        rv = client.get(f'/p/{private_paste.slug}')
        assert rv.status_code == 200

    def test_expired_paste_returns_410(self, app, client):
        from app.extensions import db
        from app.models import Paste

        past = datetime.now(timezone.utc) - timedelta(hours=2)
        paste = Paste(slug='expiredslug', content='gone', expires_at=past)
        db.session.add(paste)
        db.session.commit()

        rv = client.get('/p/expiredslug')
        assert rv.status_code == 410

    def test_password_form_shown_for_protected_paste(self, app, client):
        from app.extensions import db
        from app.models import Paste
        from werkzeug.security import generate_password_hash

        paste = Paste(
            slug='protectedpaste',
            content='encrypted_content_placeholder',
            password_hash=generate_password_hash('hunter2'),
        )
        db.session.add(paste)
        db.session.commit()

        rv = client.get('/p/protectedpaste')
        assert rv.status_code == 200
        assert b'password' in rv.data.lower()

    def test_incorrect_password_shows_error(self, app, client):
        from app.extensions import db
        from app.models import Paste
        from werkzeug.security import generate_password_hash

        paste = Paste(
            slug='wrongpw',
            content='encrypted_content_placeholder',
            password_hash=generate_password_hash('correctpassword'),
        )
        db.session.add(paste)
        db.session.commit()

        rv = client.post('/p/wrongpw', data={'password': 'wrongpassword'}, follow_redirects=True)
        assert rv.status_code == 200
        assert b'Incorrect password' in rv.data


class TestRawPasteRoute:
    def test_get_raw_content(self, client, sample_paste):
        rv = client.get(f'/p/{sample_paste.slug}/raw')
        assert rv.status_code == 200
        assert rv.content_type.startswith('text/plain')
        assert b'Hello, world!' in rv.data

    def test_raw_nonexistent_returns_404(self, client):
        rv = client.get('/p/nosuchpaste/raw')
        assert rv.status_code == 404

    def test_raw_password_protected_without_session_returns_403(self, app, client):
        from app.extensions import db
        from app.models import Paste
        from werkzeug.security import generate_password_hash

        paste = Paste(
            slug='rawprotected',
            content='encrypted_placeholder',
            password_hash=generate_password_hash('secret'),
        )
        db.session.add(paste)
        db.session.commit()

        rv = client.get('/p/rawprotected/raw')
        assert rv.status_code == 403


class TestForkPasteRoute:
    def test_fork_returns_prefilled_form(self, client, sample_paste):
        rv = client.get(f'/p/{sample_paste.slug}/fork')
        assert rv.status_code == 200
        assert b'Hello, world!' in rv.data

    def test_fork_nonexistent_returns_404(self, client):
        rv = client.get('/p/nosuchpaste/fork')
        assert rv.status_code == 404


class TestSearchRoute:
    def test_get_search_page(self, client):
        rv = client.get('/search')
        assert rv.status_code == 200

    def test_search_returns_matching_public_paste(self, client, sample_paste):
        rv = client.get('/search?q=Hello')
        assert rv.status_code == 200
        assert b'Test Paste' in rv.data

    def test_search_no_results(self, client):
        rv = client.get('/search?q=zzznomatch9999')
        assert rv.status_code == 200

    def test_search_empty_query(self, client):
        rv = client.get('/search?q=')
        assert rv.status_code == 200

    def test_private_paste_excluded_from_search(self, client, private_paste):
        rv = client.get('/search?q=Secret')
        assert b'Private Paste' not in rv.data


class TestAttachmentServing:
    """Regression: uploaded files must never render inline as active content."""

    def _make_paste_with_attachment(self, app, filename, body=b'x'):
        import os
        import secrets
        from app.extensions import db
        from app.models import Attachment, Paste

        paste = Paste(slug='attslug1', title='Att', content='c',
                      language='plaintext', is_private=False, burn_after_read=False)
        db.session.add(paste)
        db.session.flush()
        ext = os.path.splitext(filename)[1]
        stored = secrets.token_hex(16) + ext
        with open(os.path.join(app.config['UPLOAD_FOLDER'], stored), 'wb') as f:
            f.write(body)
        att = Attachment(paste_id=paste.id, original_filename=filename,
                         stored_filename=stored, file_size=len(body))
        db.session.add(att)
        db.session.commit()
        return paste.slug, att.id

    def test_html_attachment_forced_to_download(self, app, client):
        slug, att_id = self._make_paste_with_attachment(
            app, 'evil.html', b'<script>alert(1)</script>')
        rv = client.get(f'/p/{slug}/view/{att_id}')
        assert rv.status_code == 200
        assert 'text/html' not in rv.headers.get('Content-Type', '')
        assert 'attachment' in rv.headers.get('Content-Disposition', '')
        assert rv.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_svg_attachment_forced_to_download(self, app, client):
        slug, att_id = self._make_paste_with_attachment(app, 'x.svg', b'<svg/>')
        rv = client.get(f'/p/{slug}/view/{att_id}')
        assert 'attachment' in rv.headers.get('Content-Disposition', '')
        assert rv.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_png_attachment_served_inline(self, app, client):
        slug, att_id = self._make_paste_with_attachment(app, 'ok.png')
        rv = client.get(f'/p/{slug}/view/{att_id}')
        assert rv.headers.get('Content-Type') == 'image/png'
        assert 'attachment' not in rv.headers.get('Content-Disposition', '')
        assert rv.headers.get('X-Content-Type-Options') == 'nosniff'
