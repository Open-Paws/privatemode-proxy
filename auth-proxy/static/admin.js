// Admin UI behaviour, served from /admin/static/admin.js so the page's
// Content-Security-Policy can forbid inline scripts entirely.
(function () {
  'use strict';

  // "Copy" button next to a newly generated key
  document.querySelectorAll('[data-copy]').forEach(function (button) {
    button.addEventListener('click', function () {
      navigator.clipboard.writeText(button.getAttribute('data-copy')).then(function () {
        button.textContent = 'Copied';
      });
    });
  });

  // Forms that ask for confirmation before submitting (e.g. deleting a key)
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.getAttribute('data-confirm'))) {
        event.preventDefault();
      }
    });
  });
})();
