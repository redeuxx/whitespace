import os
import pytest


class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key-not-for-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'testpassword'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads_test')
    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_ATTACHMENTS = 10
    RATE_LIMIT_PASTE = '1000 per hour'
    RATE_LIMIT_SEARCH = '1000 per hour'
    PASTES_PER_PAGE = 20
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class TestConfigCsrfEnabled(TestConfig):
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None


@pytest.fixture(scope='function')
def app():
    from app import create_app, _seed_settings
    from app.extensions import db as _db

    flask_app = create_app(config_class=TestConfig)
    with flask_app.app_context():
        _db.create_all()
        _seed_settings()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def csrf_app():
    from app import create_app, _seed_settings
    from app.extensions import db as _db

    flask_app = create_app(config_class=TestConfigCsrfEnabled)
    with flask_app.app_context():
        _db.create_all()
        _seed_settings()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client(use_cookies=True)


@pytest.fixture
def admin_client(app):
    c = app.test_client()
    c.post('/admin/login', data={
        'username': 'admin',
        'password': 'testpassword',
    }, follow_redirects=True)
    return c


@pytest.fixture
def sample_paste(app):
    from app.extensions import db
    from app.models import Paste

    paste = Paste(
        slug='testslug1',
        title='Test Paste',
        content='Hello, world!',
        language='plaintext',
        is_private=False,
        burn_after_read=False,
    )
    db.session.add(paste)
    db.session.commit()
    return paste


@pytest.fixture
def private_paste(app):
    from app.extensions import db
    from app.models import Paste

    paste = Paste(
        slug='privateslug',
        title='Private Paste',
        content='Secret content',
        language='plaintext',
        is_private=True,
        burn_after_read=False,
    )
    db.session.add(paste)
    db.session.commit()
    return paste
