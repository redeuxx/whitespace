"""Resource and concurrency hardening: file cleanup, burn claim, size caps, bans, URL titles."""
import io
import os
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer


def _new_paste(client, **data):
    data.setdefault('content', 'hello hardening tests')
    rv = client.post('/new', data=data, content_type='multipart/form-data')
    return rv.headers['Location'].rsplit('/', 1)[1]


def _stored_files(app, slug):
    from app.models import Paste
    paste = Paste.query.filter_by(slug=slug).one()
    return [os.path.join(app.config['UPLOAD_FOLDER'], a.stored_filename) for a in paste.attachments]


def test_burn_view_deletes_attachment_files(app, client):
    slug = _new_paste(client, expiry='burn', attachments=(io.BytesIO(b'data'), 'a.txt'))
    files = _stored_files(app, slug)
    assert files and all(os.path.exists(f) for f in files)

    reader = app.test_client()
    assert reader.get(f'/p/{slug}').status_code == 200
    assert not any(os.path.exists(f) for f in files)
    assert reader.get(f'/p/{slug}').status_code == 404


def test_burn_view_that_loses_the_claim_gets_410(app, client, monkeypatch):
    from app.extensions import db
    from app.models import Paste
    slug = _new_paste(client, expiry='burn')

    # Simulate a concurrent viewer deleting the row between our SELECT and DELETE.
    real_execute = db.session.execute

    def racing_execute(stmt, *args, **kwargs):
        if getattr(stmt, 'is_delete', False):
            real_execute(db.delete(Paste).where(Paste.slug == slug))
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db.session, 'execute', racing_execute)
    rv = app.test_client().get(f'/p/{slug}')
    assert rv.status_code == 410
    assert b'hello hardening tests' not in rv.data


def test_expired_view_deletes_attachment_files(app, client):
    from app.extensions import db
    from app.models import Paste, utcnow
    slug = _new_paste(client, attachments=(io.BytesIO(b'data'), 'a.txt'))
    files = _stored_files(app, slug)
    Paste.query.filter_by(slug=slug).one().expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()

    assert client.get(f'/p/{slug}').status_code == 410
    assert not any(os.path.exists(f) for f in files)


def test_urlencoded_content_over_form_cap_is_rejected(app, client):
    from app.models import Paste
    big = 'x' * (app.config['MAX_FORM_MEMORY_SIZE'] + 1)
    rv = client.post('/new', data={'content': big})
    assert rv.status_code == 413
    assert Paste.query.count() == 0


def test_expired_bans_are_pruned_and_active_ones_enforced(app, client):
    from app.extensions import db
    from app.models import BannedIP, utcnow
    db.session.add(BannedIP(ip_address='127.0.0.1', expires_at=utcnow() - timedelta(hours=1)))
    db.session.add(BannedIP(ip_address='10.0.0.0/8', expires_at=None))
    db.session.commit()

    assert client.get('/').status_code == 200
    assert [b.ip_address for b in BannedIP.query.all()] == ['10.0.0.0/8']
    assert client.get('/', environ_base={'REMOTE_ADDR': '10.1.2.3'}).status_code == 403


def test_url_title_fetch_does_not_follow_redirects(monkeypatch):
    from app import utils

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/start':
                self.send_response(302)
                self.send_header('Location', '/target')
                self.end_headers()
            else:
                body = b'<title>reached redirect target</title>'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    # Let the loopback test server through the private-IP check.
    monkeypatch.setattr(utils, '_resolve_safe_host',
                        lambda url: ('127.0.0.1', utils.urlparse(url)))
    try:
        assert utils.fetch_url_title(f'http://example.test:{port}/target') == 'reached redirect target'
        assert utils.fetch_url_title(f'http://example.test:{port}/start') is None
    finally:
        server.shutdown()
