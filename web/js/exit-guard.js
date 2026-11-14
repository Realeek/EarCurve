/* exit-guard.js — 退出确认（无依赖）
   页面通过 document.body 的 data-dirty="1" 标记存在未完成进度。
   网页版：右上角自绘 X → 自定义确认框；桌面版可注入 window.closeAppWindow 接管。 */
(function (global) {
  'use strict';

  var overlay = null;
  var cancelBtn = null;
  var confirmBtn = null;
  var lastFocus = null;

  function isDirty() {
    return document.body.getAttribute('data-dirty') === '1';
  }

  function build() {
    overlay = document.createElement('div');
    overlay.className = 'modal-backdrop hidden';
    overlay.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true" aria-labelledby="exit-modal-title">' +
        '<h2 id="exit-modal-title" data-i18n="common.exitTitle">退出确认</h2>' +
        '<p data-i18n="common.exitBody">当前测试或导出尚未完成。退出后将丢失本次进度，确定要退出吗？</p>' +
        '<div class="modal-actions">' +
          '<button type="button" class="btn ghost" data-action="cancel" data-i18n="common.cancel">取消</button>' +
          '<button type="button" class="btn primary" data-action="confirm" data-i18n="common.exitConfirm">确认退出</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    cancelBtn = overlay.querySelector('[data-action="cancel"]');
    confirmBtn = overlay.querySelector('[data-action="confirm"]');

    if (global.I18N && I18N.apply) I18N.apply(overlay);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });
    cancelBtn.addEventListener('click', closeModal);
    confirmBtn.addEventListener('click', exitNow);
    document.addEventListener('keydown', function (e) {
      if (!overlay || overlay.classList.contains('hidden')) return;
      if (e.key === 'Escape') {
        closeModal();
        return;
      }
      if (e.key !== 'Tab') return;
      var focusable = overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  function openModal() {
    if (!overlay) build();
    lastFocus = document.activeElement;
    overlay.classList.remove('hidden');
    document.body.classList.add('modal-open');
    if (cancelBtn) cancelBtn.focus();
  }

  function closeModal() {
    if (!overlay) return;
    overlay.classList.add('hidden');
    document.body.classList.remove('modal-open');
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    lastFocus = null;
  }

  function exitNow() {
    closeModal();
    document.body.removeAttribute('data-dirty');
    if (typeof global.closeAppWindow === 'function') {
      global.closeAppWindow();
      return;
    }
    try { global.close(); } catch (e) {}
    /* 浏览器通常不允许脚本关闭非脚本打开的标签页，退回主界面 */
    setTimeout(function () {
      global.location.href = 'index.html?home=1';
    }, 120);
  }

  function addWindowButton() {
    var bar = document.querySelector('.topbar');
    if (!bar) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'win-close';
    btn.innerHTML = '&times;';
    function syncLabel() {
      var label = (global.I18N && I18N.t) ? I18N.t('common.close') : 'Close';
      btn.setAttribute('aria-label', label);
      btn.title = label;
    }
    syncLabel();
    document.addEventListener('langchange', syncLabel);
    btn.addEventListener('click', function () {
      if (isDirty()) {
        btn.focus();
        openModal();
      } else {
        exitNow();
      }
    });
    bar.appendChild(btn);
  }

  global.addEventListener('beforeunload', function (e) {
    if (!isDirty()) return;
    e.preventDefault();
    e.returnValue = '';
  });

  /* 供桌面壳（PySide6 / Electron）调用：
     runJavaScript("EQExitGuard.isDirty()") 判断是否弹确认；
     页面内确认框可复用 EQExitGuard.openConfirm()。 */
  global.EQExitGuard = {
    isDirty: isDirty,
    openConfirm: openModal,
    closeConfirm: closeModal,
    exit: exitNow
  };

  document.addEventListener('langchange', function () {
    if (overlay && global.I18N && I18N.apply) I18N.apply(overlay);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addWindowButton);
  } else {
    addWindowButton();
  }
})(window);
