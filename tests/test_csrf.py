"""
CSRF protection tests.

Primary coverage: flask-wtf 1.2.2 -> 1.3.0 and wtforms 3.2.1 -> 3.2.2

These tests use csrf_app / csrf_client (WTF_CSRF_ENABLED=True) to verify:
1. POST requests without a CSRF token are rejected with 400.
2. POST requests with a garbage token are rejected with 400.
3. POST requests with a valid token extracted from the GET response succeed.
4. A token generated in one session is rejected in a different session.

Token extraction: the Jinja template renders {{ csrf_token() }} into a hidden
input. We GET the form page, parse the token, then replay it in the POST.
The test_client(use_cookies=True) preserves the session so the server can
validate the token against the session that generated it.
"""
import re
import pytest


def _extract_csrf_token(data: bytes) -> str:
    m = re.search(rb'name="csrf_token"\s+value="([^"]+)"', data)
    if not m:
        m = re.search(rb'value="([^"]+)"\s+name="csrf_token"', data)
    assert m is not None, (
        'CSRF token not found in response. '
        'Ensure WTF_CSRF_ENABLED=True and the template renders {{ csrf_token() }}.'
    )
    return m.group(1).decode()


class TestCsrfOnNewPaste:
    def test_post_without_token_returns_400(self, csrf_client):
        rv = csrf_client.post('/new', data={'content': 'hello'})
        assert rv.status_code == 400

    def test_post_with_garbage_token_returns_400(self, csrf_client):
        rv = csrf_client.post('/new', data={
            'content': 'hello',
            'csrf_token': 'this-is-not-a-real-token',
        })
        assert rv.status_code == 400

    def test_post_with_valid_token_succeeds(self, csrf_client):
        rv_get = csrf_client.get('/new')
        assert rv_get.status_code == 200

        token = _extract_csrf_token(rv_get.data)

        rv_post = csrf_client.post('/new', data={
            'content': 'CSRF-validated paste content',
            'csrf_token': token,
        }, follow_redirects=False)

        assert rv_post.status_code == 302
        assert '/p/' in rv_post.headers['Location']

    def test_token_from_different_session_rejected(self, csrf_app):
        client_a = csrf_app.test_client(use_cookies=True)
        client_b = csrf_app.test_client(use_cookies=True)

        token_from_a = _extract_csrf_token(client_a.get('/new').data)

        rv = client_b.post('/new', data={
            'content': 'cross-session attack',
            'csrf_token': token_from_a,
        })
        assert rv.status_code == 400


class TestCsrfOnAdminLogin:
    def test_post_without_token_returns_400(self, csrf_client):
        rv = csrf_client.post('/admin/login', data={
            'username': 'admin',
            'password': 'testpassword',
        })
        assert rv.status_code == 400

    def test_post_with_garbage_token_returns_400(self, csrf_client):
        rv = csrf_client.post('/admin/login', data={
            'username': 'admin',
            'password': 'testpassword',
            'csrf_token': 'garbage',
        })
        assert rv.status_code == 400

    def test_post_with_valid_token_succeeds(self, csrf_client):
        rv_get = csrf_client.get('/admin/login')
        assert rv_get.status_code == 200

        token = _extract_csrf_token(rv_get.data)

        rv_post = csrf_client.post('/admin/login', data={
            'username': 'admin',
            'password': 'testpassword',
            'csrf_token': token,
        }, follow_redirects=False)

        assert rv_post.status_code == 302
        assert '/admin' in rv_post.headers['Location']


class TestCsrfTokenPresence:
    """
    Verify that CSRFProtect.init_app() completed successfully after the
    flask-wtf bump and that the csrf_token() Jinja function is registered.
    """

    def test_token_present_in_new_paste_form(self, csrf_client):
        rv = csrf_client.get('/new')
        assert rv.status_code == 200
        token = _extract_csrf_token(rv.data)
        assert len(token) > 20

    def test_token_present_in_admin_login_form(self, csrf_client):
        rv = csrf_client.get('/admin/login')
        assert rv.status_code == 200
        token = _extract_csrf_token(rv.data)
        assert len(token) > 20

    def test_token_is_non_empty_string(self, csrf_client):
        # Tokens are HMAC-based; we just verify the function returns something usable.
        token_a = _extract_csrf_token(csrf_client.get('/new').data)
        token_b = _extract_csrf_token(csrf_client.get('/admin/login').data)
        assert len(token_a) > 20
        assert len(token_b) > 20
