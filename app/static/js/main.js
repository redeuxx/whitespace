/* ── Whitespace — main.js ── */

function initWhitespace() {

  // THEME TOGGLE
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  const hljsDark = document.getElementById('hljs-theme-dark');
  const hljsLight = document.getElementById('hljs-theme-light');

  function applyTheme(theme) {
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

  // ── Navbar burger toggle ────────────────────────────────────────────────────
  const burgers = document.querySelectorAll('.navbar-burger');
  burgers.forEach(burger => {
    burger.addEventListener('click', () => {
      const target = document.getElementById(burger.dataset.target);
      burger.classList.toggle('is-active');
      target?.classList.toggle('is-active');
    });
  });

  // ── Flash message dismiss ───────────────────────────────────────────────────
  document.querySelectorAll('.notification .delete').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.notification').remove());
  });

  // ── Syntax highlighting + line numbers ──────────────────────────────────────
  document.querySelectorAll('pre code.hljs-target').forEach(block => {
    hljs.highlightElement(block);
    const text = block.innerText;
    const count = text.endsWith('\n') ? text.split('\n').length - 1 : text.split('\n').length;
    const gutter = document.createElement('div');
    gutter.className = 'line-numbers';
    gutter.setAttribute('aria-hidden', 'true');
    gutter.textContent = Array.from({length: count}, (_, i) => i + 1).join('\n');
    block.closest('pre').prepend(gutter);
    // Mirror exact computed metrics from the code element so alignment is pixel-perfect
    const cs = window.getComputedStyle(block);
    gutter.style.lineHeight = cs.lineHeight;
    gutter.style.fontSize   = cs.fontSize;
    gutter.style.paddingTop = cs.paddingTop;
    gutter.style.paddingBottom = cs.paddingBottom;
  });

  // ── Copy to clipboard ───────────────────────────────────────────────────────
  const copyBtn = document.getElementById('copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const codeEl = document.querySelector('pre code');
      if (!codeEl) return;
      navigator.clipboard.writeText(codeEl.innerText).then(() => {
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

  // ── Copy link to clipboard ───────────────────────────────────────────────────
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

  // ── Language selector — show/hide auto-detect hint ─────────────────────────
  const langSelect = document.getElementById('language-select');
  const langHint = document.getElementById('lang-auto-hint');
  if (langSelect && langHint) {
    langSelect.addEventListener('change', () => {
      langHint.style.display = langSelect.value === '' ? 'block' : 'none';
    });
  }

  // ── Password visibility toggle ──────────────────────────────────────────────
  document.querySelectorAll('.toggle-password').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const isHidden = target.type === 'password';
      target.type = isHidden ? 'text' : 'password';
      const icon = btn.querySelector('i');
      icon?.classList.toggle('fa-eye', !isHidden);
      icon?.classList.toggle('fa-eye-slash', isHidden);
    });
  });

  // ── File attachment list preview ────────────────────────────────────────────
  const fileInput = document.getElementById('attachments');
  const fileList = document.getElementById('file-list');
  const maxFiles = parseInt(fileList?.dataset.max || '10');

  if (fileInput && fileList) {
    fileInput.addEventListener('change', () => {
      fileList.innerHTML = '';
      const files = Array.from(fileInput.files).slice(0, maxFiles);
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

      if (fileInput.files.length > maxFiles) {
        const warn = document.createElement('p');
        warn.className = 'help is-warning';
        warn.textContent = `Only the first ${maxFiles} files will be uploaded.`;
        fileList.appendChild(warn);
      }
    });
  }

  // ── Confirm dangerous actions ───────────────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ── Burn-after-read warning ─────────────────────────────────────────────────
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

// ── Helpers ─────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
