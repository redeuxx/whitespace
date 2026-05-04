import ipaddress
import os
from datetime import datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, make_response,
    redirect, render_template, request, send_from_directory,
    session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, limiter
from ..models import Attachment, BannedIP, Paste, SiteSetting
from ..utils import (
    EXPIRY_OPTIONS, HLJS_LANGUAGES, decrypt_content, detect_language,
    encrypt_content, extract_title, fetch_url_title, generate_slug, is_single_url,
    parse_expiry, save_attachment, time_ago, time_until,
)

main_bp = Blueprint('main', __name__)


def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


@main_bp.before_request
def check_banned():
    ip = get_client_ip()
    try:
        client = ipaddress.ip_address(ip)
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


@main_bp.context_processor
def inject_globals():
    from app import __version__
    return {
        'site_name': SiteSetting.get('site_name', 'Whitespace'),
        'site_description': SiteSetting.get('site_description', 'A simple, clean pastebin.'),
        'public_listing_enabled': SiteSetting.get('public_listing_enabled', 'true') == 'true',
        'time_ago': time_ago,
        'time_until': time_until,
        'max_attachments': current_app.config['MAX_ATTACHMENTS'],
        'app_version': __version__,
    }


# INDEX

@main_bp.route('/')
def index():
    public_listing = SiteSetting.get('public_listing_enabled', 'true') == 'true'
    page = request.args.get('page', 1, type=int)
    now = datetime.now(timezone.utc)

    if public_listing:
        query = Paste.query.filter(
            Paste.is_private == False,  # noqa: E712
            Paste.burn_after_read == False,  # noqa: E712
            db.or_(Paste.expires_at.is_(None), Paste.expires_at > now),
        ).order_by(Paste.created_at.desc())
        pagination = query.paginate(
            page=page,
            per_page=current_app.config['PASTES_PER_PAGE'],
            error_out=False,
        )
        pastes = pagination.items
    else:
        pagination = None
        pastes = []

    return render_template(
        'index.html',
        pastes=pastes,
        pagination=pagination,
        public_listing=public_listing,
    )


# NEW PASTE

@main_bp.route('/new', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config['RATE_LIMIT_PASTE'], methods=['POST'])
def new_paste():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Paste content cannot be empty.', 'danger')
            return render_template('new_paste.html', expiry_options=EXPIRY_OPTIONS,
                                   languages=HLJS_LANGUAGES, form=request.form)

        title = request.form.get('title', '').strip()
        language = request.form.get('language', '').strip()
        is_private = request.form.get('visibility') == 'private'
        password = request.form.get('password', '').strip()
        expiry_str = request.form.get('expiry', 'never')

        if not title and not password:
            if is_single_url(content):
                title = fetch_url_title(content.strip()) or extract_title(content)
            else:
                title = extract_title(content)

        if not language or language == 'auto':
            language = detect_language(content)

        expires_at, burn_after_read = parse_expiry(expiry_str)
        password_hash = generate_password_hash(password) if password else None

        slug = generate_slug()
        if password:
            content = encrypt_content(content, password, slug, current_app.config['SECRET_KEY'])

        paste = Paste(
            slug=slug,
            title=title,
            content=content,
            language=language,
            is_private=is_private,
            password_hash=password_hash,
            expires_at=expires_at,
            burn_after_read=burn_after_read,
            ip_address=get_client_ip(),
        )
        db.session.add(paste)
        db.session.flush()  # get paste.id before saving attachments

        files = request.files.getlist('attachments')
        max_att = current_app.config['MAX_ATTACHMENTS']
        max_size = current_app.config['MAX_FILE_SIZE']
        upload_folder = current_app.config['UPLOAD_FOLDER']
        saved = 0

        for f in files:
            if not f or not f.filename:
                continue
            if saved >= max_att:
                flash(f'Maximum {max_att} attachments allowed. Some files were skipped.', 'warning')
                break
            f.seek(0, 2)
            size = f.tell()
            f.seek(0)
            if size > max_size:
                flash(
                    f'File "{f.filename}" exceeds the {max_size // (1024*1024)} MB limit and was skipped.',
                    'warning',
                )
                continue
            original, stored, file_size = save_attachment(f, upload_folder)
            att = Attachment(
                paste_id=paste.id,
                original_filename=original,
                stored_filename=stored,
                file_size=file_size,
            )
            db.session.add(att)
            saved += 1

        db.session.commit()

        if password:
            paste_passwords = session.get('paste_passwords', {})
            paste_passwords[paste.slug] = password
            session['paste_passwords'] = paste_passwords
            session.modified = True

        # Give the creator a one-time session token so their redirect view doesn't burn the paste
        if burn_after_read:
            previews = session.get('burn_previews', [])
            previews.append(paste.slug)
            session['burn_previews'] = previews
            session.modified = True

        if is_single_url(content):
            creator_views = session.get('url_creator_views', [])
            creator_views.append(paste.slug)
            session['url_creator_views'] = creator_views
            session.modified = True
        return redirect(url_for('main.view_paste', slug=paste.slug))

    return render_template('new_paste.html', expiry_options=EXPIRY_OPTIONS,
                           languages=HLJS_LANGUAGES, form={})


# VIEW PASTE

@main_bp.route('/p/<slug>', methods=['GET', 'POST'])
def view_paste(slug):
    paste = Paste.query.filter_by(slug=slug).first_or_404()

    if paste.is_expired:
        db.session.delete(paste)
        db.session.commit()
        abort(410)

    # Password check
    unlocked = slug in session.get('unlocked_pastes', [])
    if paste.is_password_protected and not unlocked:
        if request.method == 'POST':
            pw = request.form.get('password', '')
            if check_password_hash(paste.password_hash, pw):
                unlocked_list = session.get('unlocked_pastes', [])
                unlocked_list.append(slug)
                session['unlocked_pastes'] = unlocked_list
                paste_passwords = session.get('paste_passwords', {})
                paste_passwords[slug] = pw
                session['paste_passwords'] = paste_passwords
                session.modified = True
                return redirect(url_for('main.view_paste', slug=slug))
            else:
                flash('Incorrect password.', 'danger')
        return render_template('password.html', paste=paste)

    if paste.is_password_protected:
        pw = session.get('paste_passwords', {}).get(slug, '')
        try:
            paste.content = decrypt_content(paste.content, pw, slug, current_app.config['SECRET_KEY'])
        except Exception:
            flash('Could not decrypt paste. Please re-enter the password.', 'danger')
            unlocked_list = session.get('unlocked_pastes', [])
            if slug in unlocked_list:
                unlocked_list.remove(slug)
            session['unlocked_pastes'] = unlocked_list
            session.modified = True
            return render_template('password.html', paste=paste)

    # Check if this is the creator's one-time preview (doesn't burn or count)
    previews = session.get('burn_previews', [])
    is_creator_preview = paste.burn_after_read and slug in previews
    if is_creator_preview:
        previews.remove(slug)
        session['burn_previews'] = previews
        session.modified = True
        if is_single_url(paste.content):
            return render_template('redirect_paste.html', paste=paste, burn_preview=True,
                                   redirect_url=paste.content.strip())
        return render_template('view_paste.html', paste=paste, burn_preview=True)

    # Increment view count
    paste.view_count += 1
    db.session.commit()

    burn = paste.burn_after_read

    if is_single_url(paste.content):
        creator_views = session.get('url_creator_views', [])
        is_url_creator = slug in creator_views
        if is_url_creator:
            creator_views.remove(slug)
            session['url_creator_views'] = creator_views
            session.modified = True
        response = make_response(render_template('redirect_paste.html', paste=paste,
                                                 burn_preview=False,
                                                 redirect_url=paste.content.strip(),
                                                 is_creator=is_url_creator))
    else:
        response = make_response(render_template('view_paste.html', paste=paste, burn_preview=False))

    if burn:
        try:
            db.session.delete(paste)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return response


# RAW VIEW

@main_bp.route('/p/<slug>/raw')
def raw_paste(slug):
    paste = Paste.query.filter_by(slug=slug).first_or_404()

    if paste.is_expired:
        abort(410)

    if paste.is_password_protected and slug not in session.get('unlocked_pastes', []):
        abort(403)

    content = paste.content
    if paste.is_password_protected:
        pw = session.get('paste_passwords', {}).get(slug, '')
        try:
            content = decrypt_content(content, pw, slug, current_app.config['SECRET_KEY'])
        except Exception:
            abort(403)

    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return response


# FORK PASTE

@main_bp.route('/p/<slug>/fork')
def fork_paste(slug):
    paste = Paste.query.filter_by(slug=slug).first_or_404()

    if paste.is_expired:
        abort(410)

    if paste.is_password_protected and slug not in session.get('unlocked_pastes', []):
        abort(403)

    content = paste.content
    if paste.is_password_protected:
        pw = session.get('paste_passwords', {}).get(slug, '')
        try:
            content = decrypt_content(content, pw, slug, current_app.config['SECRET_KEY'])
        except Exception:
            abort(403)

    return render_template(
        'new_paste.html',
        expiry_options=EXPIRY_OPTIONS,
        languages=HLJS_LANGUAGES,
        fork=paste,
        form={
            'title': f'Fork of {paste.title}',
            'content': content,
            'language': paste.language or '',
        },
    )


# DOWNLOAD ATTACHMENT

@main_bp.route('/p/<slug>/download/<int:attachment_id>')
def download_attachment(slug, attachment_id):
    paste = Paste.query.filter_by(slug=slug).first_or_404()

    if paste.is_expired:
        abort(410)

    if paste.is_password_protected and slug not in session.get('unlocked_pastes', []):
        abort(403)

    att = Attachment.query.filter_by(id=attachment_id, paste_id=paste.id).first_or_404()
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        att.stored_filename,
        as_attachment=True,
        download_name=att.original_filename,
    )


# VIEW ATTACHMENT (inline, for lightbox)

@main_bp.route('/p/<slug>/view/<int:attachment_id>')
def view_attachment(slug, attachment_id):
    paste = Paste.query.filter_by(slug=slug).first_or_404()

    if paste.is_expired:
        abort(410)

    if paste.is_password_protected and slug not in session.get('unlocked_pastes', []):
        abort(403)

    att = Attachment.query.filter_by(id=attachment_id, paste_id=paste.id).first_or_404()
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        att.stored_filename,
        as_attachment=False,
        download_name=att.original_filename,
    )


# SEARCH

@main_bp.route('/search')
@limiter.limit(lambda: current_app.config['RATE_LIMIT_SEARCH'])
def search():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    results = None
    pagination = None

    if query:
        now = datetime.now(timezone.utc)
        base = Paste.query.filter(
            Paste.is_private == False,  # noqa: E712
            Paste.burn_after_read == False,  # noqa: E712
            db.or_(Paste.expires_at.is_(None), Paste.expires_at > now),
            db.or_(
                Paste.title.ilike(f'%{query}%'),
                Paste.content.ilike(f'%{query}%'),
            ),
        ).order_by(Paste.created_at.desc())

        pagination = base.paginate(
            page=page,
            per_page=current_app.config['PASTES_PER_PAGE'],
            error_out=False,
        )
        results = pagination.items

    return render_template('search.html', query=query, results=results, pagination=pagination)
