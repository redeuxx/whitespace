from datetime import datetime, timezone
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Paste(db.Model):
    __tablename__ = 'pastes'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50))
    is_private = db.Column(db.Boolean, default=False, nullable=False)
    password_hash = db.Column(db.String(256))
    expires_at = db.Column(db.DateTime(timezone=True))
    burn_after_read = db.Column(db.Boolean, default=False, nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    ip_address = db.Column(db.String(45))
    parent_slug = db.Column(db.String(20))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    attachments = db.relationship(
        'Attachment', backref='paste', lazy=True, cascade='all, delete-orphan'
    )

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires

    @property
    def is_password_protected(self):
        return self.password_hash is not None

    def __repr__(self):
        return f'<Paste {self.slug}>'


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    paste_id = db.Column(db.Integer, db.ForeignKey('pastes.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    @property
    def size_human(self):
        size = self.file_size or 0
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def __repr__(self):
        return f'<Attachment {self.original_filename}>'


class BannedIP(db.Model):
    __tablename__ = 'banned_ips'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    reason = db.Column(db.String(500))
    banned_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f'<BannedIP {self.ip_address}>'


class SiteSetting(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        setting = SiteSetting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = SiteSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SiteSetting(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

    def __repr__(self):
        return f'<SiteSetting {self.key}={self.value}>'
