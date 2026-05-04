declare const hljs: {
  highlightElement(block: Element): void;
};

function initWhitespace(): void {

  // THEME TOGGLE
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  const hljsDark = document.getElementById('hljs-theme-dark') as HTMLLinkElement | null;
  const hljsLight = document.getElementById('hljs-theme-light') as HTMLLinkElement | null;

  function applyTheme(theme: string): void {
    document.documentElement.setAttribute('data-theme', theme);
    if (themeIcon) {
      themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
    if (hljsDark) hljsDark.disabled = (theme === 'light');
    if (hljsLight) hljsLight.disabled = (theme === 'dark');
  }

  applyTheme(document.documentElement.getAttribute('data-theme') || 'dark');

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const next = (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark';
      localStorage.setItem('ws-theme', next);
      applyTheme(next);
    });
  }

  // NAVBAR BURGER TOGGLE
  const burgers = document.querySelectorAll('.navbar-burger');
  burgers.forEach(burger => {
    burger.addEventListener('click', () => {
      const targetId = (burger as HTMLElement).dataset.target;
      if (!targetId) return;
      const target = document.getElementById(targetId);
      burger.classList.toggle('is-active');
      target?.classList.toggle('is-active');
    });
  });

  // FLASH MESSAGE DISMISS
  document.querySelectorAll('.notification .delete').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.notification')?.remove());
  });

  // SYNTAX HIGHLIGHTING + LINE NUMBERS
  document.querySelectorAll('pre code.hljs-target').forEach(block => {
    hljs.highlightElement(block);
    const text = (block as HTMLElement).innerText;
    const count = text.endsWith('\n') ? text.split('\n').length - 1 : text.split('\n').length;
    const gutter = document.createElement('div');
    gutter.className = 'line-numbers';
    gutter.setAttribute('aria-hidden', 'true');
    gutter.textContent = Array.from({length: count}, (_, i) => i + 1).join('\n');
    block.closest('pre')?.prepend(gutter);
    const cs = window.getComputedStyle(block as HTMLElement);
    gutter.style.lineHeight = cs.lineHeight;
    gutter.style.fontSize   = cs.fontSize;
    gutter.style.paddingTop = cs.paddingTop;
    gutter.style.paddingBottom = cs.paddingBottom;
  });

  // COPY TO CLIPBOARD
  const copyBtn = document.getElementById('copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const codeEl = document.querySelector('pre code');
      if (!codeEl) return;
      navigator.clipboard.writeText((codeEl as HTMLElement).innerText).then(() => {
        const original = copyBtn.innerHTML;
        copyBtn.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Copied!</span>';
        copyBtn.classList.add('is-success');
        setTimeout(() => {
          copyBtn.innerHTML = original;
          copyBtn.classList.remove('is-success');
        }, 2000);
      });
    });
  }

  // COPY LINK TO CLIPBOARD
  const copyLinkBtn = document.getElementById('copy-link-btn');
  if (copyLinkBtn) {
    copyLinkBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(window.location.href).then(() => {
        const original = copyLinkBtn.innerHTML;
        copyLinkBtn.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Copied!</span>';
        copyLinkBtn.classList.add('is-success');
        setTimeout(() => {
          copyLinkBtn.innerHTML = original;
          copyLinkBtn.classList.remove('is-success');
        }, 2000);
      });
    });
  }

  // LANGUAGE SELECTOR
  const langSelect = document.getElementById('language-select') as HTMLSelectElement | null;
  const langHint = document.getElementById('lang-auto-hint');
  if (langSelect && langHint) {
    langSelect.addEventListener('change', () => {
      (langHint as HTMLElement).style.display = langSelect.value === '' ? 'block' : 'none';
    });
  }

  // PASSWORD VISIBILITY TOGGLE
  document.querySelectorAll<HTMLElement>('.toggle-password').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.target;
      if (!targetId) return;
      const target = document.getElementById(targetId) as HTMLInputElement | null;
      if (!target) return;
      const isHidden = target.type === 'password';
      target.type = isHidden ? 'text' : 'password';
      const icon = btn.querySelector('i');
      icon?.classList.toggle('fa-eye', !isHidden);
      icon?.classList.toggle('fa-eye-slash', isHidden);
    });
  });

  // FILE ATTACHMENT PREVIEW
  const fileInput = document.getElementById('attachments') as HTMLInputElement | null;
  const fileList = document.getElementById('file-list') as HTMLElement | null;
  const maxFiles = parseInt(fileList?.dataset.max ?? '10');

  if (fileInput && fileList) {
    fileInput.addEventListener('change', () => {
      fileList.innerHTML = '';
      const files = Array.from(fileInput.files ?? []).slice(0, maxFiles);
      if (files.length === 0) return;

      files.forEach(file => {
        const item = document.createElement('div');
        item.className = 'attachment-item';
        item.innerHTML = `
          <span class="icon has-text-info"><i class="fas fa-paperclip"></i></span>
          <span class="attachment-name">${escapeHtml(file.name)}</span>
          <span class="attachment-size">${formatBytes(file.size)}</span>
        `;
        fileList.appendChild(item);
      });

      if ((fileInput.files?.length ?? 0) > maxFiles) {
        const warn = document.createElement('p');
        warn.className = 'help is-warning';
        warn.textContent = `Only the first ${maxFiles} files will be uploaded.`;
        fileList.appendChild(warn);
      }
    });
  }

  // IMAGE LIGHTBOX
  const lightbox = document.getElementById('image-lightbox');
  const lightboxImg = document.getElementById('lightbox-img') as HTMLImageElement | null;
  const lightboxCaption = document.getElementById('lightbox-caption');
  const lightboxClose = lightbox?.querySelector('.ws-lightbox-close');
  const lightboxBackdrop = lightbox?.querySelector('.ws-lightbox-backdrop');

  function openLightbox(url: string, name: string): void {
    if (!lightbox || !lightboxImg || !lightboxCaption) return;
    lightboxImg.src = url;
    lightboxImg.alt = name;
    lightboxCaption.textContent = name;
    lightbox.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox(): void {
    if (!lightbox || !lightboxImg) return;
    lightbox.style.display = 'none';
    lightboxImg.src = '';
    document.body.style.overflow = '';
  }

  document.querySelectorAll<HTMLElement>('.attachment-image-trigger').forEach(el => {
    el.addEventListener('click', () => {
      const url = el.dataset.lightboxUrl;
      const name = el.dataset.lightboxName ?? '';
      if (url) openLightbox(url, name);
    });
  });

  lightboxClose?.addEventListener('click', closeLightbox);
  lightboxBackdrop?.addEventListener('click', closeLightbox);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && lightbox?.style.display === 'flex') closeLightbox();
  });

  // CONFIRM DANGEROUS ACTIONS
  document.querySelectorAll<HTMLElement>('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      const msg = el.dataset.confirm;
      if (msg && !confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  // BURN-AFTER-READ WARNING
  const burnWarning = document.getElementById('burn-warning');
  if (burnWarning) {
    setTimeout(() => burnWarning.classList.add('is-hidden'), 8000);
  }

}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWhitespace);
} else {
  initWhitespace();
}

// HELPERS

function escapeHtml(str: string): string {
  return str.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  } as Record<string, string>)[c]);
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
