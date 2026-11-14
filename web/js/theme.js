/* theme.js — 主题持久化（在 CSS 之前同步加载，避免闪烁） */
(function (global) {
  'use strict';
  var KEY = 'darkrim.eq.theme';

  function read() {
    try {
      var v = global.localStorage.getItem(KEY);
      return v === 'light' ? 'light' : 'dark';
    } catch (e) {
      return 'dark';
    }
  }

  function apply(theme) {
    theme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#f6f5fa' : '#0b0b10');
    try { global.localStorage.setItem(KEY, theme); } catch (e) {}
    return theme;
  }

  apply(read());

  global.EQTheme = {
    get: function () {
      return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    },
    set: apply,
    isLight: function () { return global.EQTheme.get() === 'light'; }
  };
})(window);
