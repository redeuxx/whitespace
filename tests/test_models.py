"""
Model and database tests.

Primary coverage: greenlet 3.3.2 -> 3.5.1
SQLAlchemy relies on greenlet for thread-local context management. A regression
surfaces as ImportError or broken session state on the first DB operation.
"""
from datetime import datetime, timedelta, timezone
import pytest


class TestPasteModel:
    def test_create_and_retrieve(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='abc123', content='hello', language='plaintext')
        db.session.add(paste)
        db.session.commit()

        fetched = Paste.query.filter_by(slug='abc123').first()
        assert fetched is not None
        assert fetched.content == 'hello'

    def test_defaults(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='def456', content='x')
        db.session.add(paste)
        db.session.commit()

        assert paste.is_private is False
        assert paste.burn_after_read is False
        assert paste.view_count == 0
        assert paste.password_hash is None

    def test_is_expired_false_when_no_expiry(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='exp1', content='x')
        db.session.add(paste)
        db.session.commit()
        assert paste.is_expired is False

    def test_is_expired_true_when_past(self, app):
        from app.extensions import db
        from app.models import Paste

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        paste = Paste(slug='exp2', content='x', expires_at=past)
        db.session.add(paste)
        db.session.commit()
        assert paste.is_expired is True

    def test_is_expired_false_when_future(self, app):
        from app.extensions import db
        from app.models import Paste

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        paste = Paste(slug='exp3', content='x', expires_at=future)
        db.session.add(paste)
        db.session.commit()
        assert paste.is_expired is False

    def test_is_password_protected_true(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='pw1', content='x', password_hash='fakehash')
        db.session.add(paste)
        db.session.commit()
        assert paste.is_password_protected is True

    def test_is_password_protected_false(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='pw2', content='x')
        db.session.add(paste)
        db.session.commit()
        assert paste.is_password_protected is False

    def test_slug_uniqueness_enforced(self, app):
        from app.extensions import db
        from app.models import Paste
        from sqlalchemy.exc import IntegrityError

        db.session.add(Paste(slug='dup', content='first'))
        db.session.commit()
        db.session.add(Paste(slug='dup', content='second'))
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_update(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='upd1', content='original')
        db.session.add(paste)
        db.session.commit()

        paste.content = 'updated'
        db.session.commit()

        fetched = Paste.query.filter_by(slug='upd1').first()
        assert fetched.content == 'updated'

    def test_delete(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='del1', content='bye')
        db.session.add(paste)
        db.session.commit()

        db.session.delete(paste)
        db.session.commit()

        assert Paste.query.filter_by(slug='del1').first() is None

    def test_view_count_increment(self, app):
        from app.extensions import db
        from app.models import Paste

        paste = Paste(slug='vc1', content='x')
        db.session.add(paste)
        db.session.commit()

        paste.view_count += 1
        db.session.commit()

        fetched = Paste.query.filter_by(slug='vc1').first()
        assert fetched.view_count == 1


class TestAttachmentModel:
    def test_create_with_paste(self, app):
        from app.extensions import db
        from app.models import Attachment, Paste

        paste = Paste(slug='att1', content='with attachment')
        db.session.add(paste)
        db.session.flush()

        att = Attachment(
            paste_id=paste.id,
            original_filename='test.txt',
            stored_filename='abcdef.txt',
            file_size=1024,
        )
        db.session.add(att)
        db.session.commit()

        fetched = Paste.query.filter_by(slug='att1').first()
        assert len(fetched.attachments) == 1
        assert fetched.attachments[0].original_filename == 'test.txt'

    def test_cascade_delete(self, app):
        from app.extensions import db
        from app.models import Attachment, Paste

        paste = Paste(slug='cas1', content='x')
        db.session.add(paste)
        db.session.flush()

        att = Attachment(
            paste_id=paste.id,
            original_filename='f.txt',
            stored_filename='g.txt',
            file_size=10,
        )
        db.session.add(att)
        db.session.commit()
        att_id = att.id

        db.session.delete(paste)
        db.session.commit()

        assert db.session.get(Attachment, att_id) is None

    def test_size_human_kb(self, app):
        from app.extensions import db
        from app.models import Attachment, Paste

        paste = Paste(slug='sh1', content='x')
        db.session.add(paste)
        db.session.flush()

        att = Attachment(
            paste_id=paste.id,
            original_filename='file.txt',
            stored_filename='stored.txt',
            file_size=2048,
        )
        db.session.add(att)
        db.session.commit()
        assert att.size_human == '2.0 KB'

    def test_size_human_bytes(self, app):
        from app.extensions import db
        from app.models import Attachment, Paste

        paste = Paste(slug='sh2', content='x')
        db.session.add(paste)
        db.session.flush()

        att = Attachment(
            paste_id=paste.id,
            original_filename='tiny.txt',
            stored_filename='tiny_s.txt',
            file_size=512,
        )
        db.session.add(att)
        db.session.commit()
        assert att.size_human == '512.0 B'


class TestBannedIPModel:
    def test_create_and_retrieve(self, app):
        from app.extensions import db
        from app.models import BannedIP

        ban = BannedIP(ip_address='10.0.0.1', reason='test ban')
        db.session.add(ban)
        db.session.commit()

        fetched = BannedIP.query.filter_by(ip_address='10.0.0.1').first()
        assert fetched is not None
        assert fetched.reason == 'test ban'

    def test_unique_ip_enforced(self, app):
        from app.extensions import db
        from app.models import BannedIP
        from sqlalchemy.exc import IntegrityError

        db.session.add(BannedIP(ip_address='10.0.0.2'))
        db.session.commit()
        db.session.add(BannedIP(ip_address='10.0.0.2'))
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_permanent_ban_has_no_expiry(self, app):
        from app.extensions import db
        from app.models import BannedIP

        ban = BannedIP(ip_address='10.0.0.3')
        db.session.add(ban)
        db.session.commit()
        assert ban.expires_at is None


class TestSiteSettingModel:
    def test_get_returns_default_when_missing(self, app):
        from app.models import SiteSetting

        val = SiteSetting.get('nonexistent_key', 'fallback')
        assert val == 'fallback'

    def test_get_returns_none_without_default(self, app):
        from app.models import SiteSetting

        assert SiteSetting.get('totally_missing') is None

    def test_get_seeded_value(self, app):
        from app.models import SiteSetting

        assert SiteSetting.get('site_name') == 'Whitespace'

    def test_set_new_key(self, app):
        from app.models import SiteSetting

        SiteSetting.set('my_test_key', 'my_value')
        assert SiteSetting.get('my_test_key') == 'my_value'

    def test_set_existing_key_updates(self, app):
        from app.models import SiteSetting

        SiteSetting.set('site_name', 'NewName')
        assert SiteSetting.get('site_name') == 'NewName'

    def test_all_seeded_defaults_present(self, app):
        from app.models import SiteSetting

        assert SiteSetting.get('site_description') is not None
        assert SiteSetting.get('public_listing_enabled') is not None
        assert SiteSetting.get('maintenance_mode') is not None
