/* eq.js — 共享模块：驱动 EQ 数据模型、JSON 读写、频响计算、曲线绘制（无依赖） */
(function (global) {
  'use strict';

  var BANDS = [40, 80, 160, 315, 630, 1000, 2000, 4000, 8000, 12000];
  var SAMPLE_RATE = 48000;
  var MIN_GAIN = -12;
  var MAX_GAIN = 12;
  var CURVE_MUSIC = 'EarCurve-Music';
  var CURVE_MOVIE = 'EarCurve-Movie';
  var CURVE_FINAL = 'EarCurve-Final';

  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function round1(v) { var r = Math.round(v * 10) / 10; return r === 0 ? 0 : r; }
  function mean(arr) {
    if (!arr.length) return 0;
    var s = 0;
    for (var i = 0; i < arr.length; i++) s += arr[i];
    return s / arr.length;
  }
  function cloneCurve(c) {
    return {
      name: c.name,
      mainGain: c.mainGain,
      bands: c.bands.map(function (b) { return { freq: b.freq, q: b.q, gain: b.gain }; })
    };
  }

  function flatCurve(name) {
    return {
      name: name || '自定义1',
      mainGain: 0,
      bands: BANDS.map(function (freq) { return { freq: freq, q: 1, gain: 0 }; })
    };
  }

  function makeCurve(name, gains, mainGain) {
    var c = flatCurve(name);
    c.bands.forEach(function (b, i) {
      b.gain = round1(clamp(Number(gains[i]) || 0, MIN_GAIN, MAX_GAIN));
    });
    c.mainGain = Math.round(Number(mainGain) || 0);
    return c;
  }

  function dbString(v) {
    var r = round1(v);
    return String(r === 0 ? 0 : r);
  }

  /* 内部曲线 → 驱动导入 JSON（字段与驱动导出样例一致） */
  function toDriverJSON(curve) {
    var sorted = curve.bands.slice().sort(function (a, b) { return a.freq - b.freq; });
    return {
      freq: sorted.map(function (b) { return String(Math.round(b.freq)); }),
      q: sorted.map(function (b) { return Number(b.q).toFixed(2); }),
      sound: sorted.map(function (b) { return dbString(b.gain); }),
      type: sorted.map(function () { return '1'; }),
      main_gain: Math.round(Number(curve.mainGain) || 0),
      name: curve.name || '自定义1'
    };
  }

  /* 驱动 JSON → 内部曲线，带校验 */
  function fromDriverJSON(obj) {
    if (!obj || typeof obj !== 'object') throw new Error('不是有效的 JSON 对象');
    ['freq', 'q', 'sound'].forEach(function (key) {
      if (!Array.isArray(obj[key])) throw new Error('缺少 "' + key + '" 数组');
    });
    var n = Math.min(obj.freq.length, obj.q.length, obj.sound.length);
    if (n === 0) throw new Error('EQ 文件里没有频段');
    var bands = [];
    for (var i = 0; i < n; i++) {
      var f = parseFloat(obj.freq[i]);
      var q = parseFloat(obj.q[i]);
      var g = parseFloat(obj.sound[i]);
      if (!isFinite(f) || f <= 0 || !isFinite(q) || q <= 0 || !isFinite(g)) {
        throw new Error('第 ' + (i + 1) + ' 段参数非法');
      }
      bands.push({ freq: f, q: q, gain: g });
    }
    return {
      bands: bands,
      mainGain: isFinite(parseFloat(obj.main_gain)) ? Math.round(parseFloat(obj.main_gain)) : 0,
      name: typeof obj.name === 'string' && obj.name ? obj.name : '自定义1'
    };
  }

  /* RBJ peaking 滤波器的幅频响应（dB） */
  function peakingResponseDb(f, band, fs) {
    fs = fs || SAMPLE_RATE;
    var nyq = fs / 2 - 1;
    var A = Math.pow(10, band.gain / 40);
    var w0 = 2 * Math.PI * Math.min(band.freq, nyq) / fs;
    var alpha = Math.sin(w0) / (2 * Math.max(band.q, 0.01));
    var b0 = 1 + alpha * A;
    var b1 = -2 * Math.cos(w0);
    var b2 = 1 - alpha * A;
    var a0 = 1 + alpha / A;
    var a1 = -2 * Math.cos(w0);
    var a2 = 1 - alpha / A;
    var w = 2 * Math.PI * Math.min(f, nyq) / fs;
    var cw = Math.cos(w), sw = Math.sin(w);
    var c2 = Math.cos(2 * w), s2 = Math.sin(2 * w);
    var numRe = b0 + b1 * cw + b2 * c2;
    var numIm = -(b1 * sw + b2 * s2);
    var denRe = a0 + a1 * cw + a2 * c2;
    var denIm = -(a1 * sw + a2 * s2);
    var mag = Math.hypot(numRe, numIm) / Math.max(1e-9, Math.hypot(denRe, denIm));
    return 20 * Math.log10(Math.max(1e-6, mag));
  }

  function curveResponseDb(curve, f, includeMain) {
    var db = includeMain ? (Number(curve.mainGain) || 0) : 0;
    for (var i = 0; i < curve.bands.length; i++) db += peakingResponseDb(f, curve.bands[i]);
    return db;
  }

  function cssVar(name, fallback) {
    try {
      var v = global.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    } catch (e) {
      return fallback;
    }
  }

  /* Canvas 画频响曲线
     series: [{ curve, color, width, dash }]
     opts: { yMin, yMax } */
  function drawCurve(canvas, series, opts) {
    opts = opts || {};
    var yMin = opts.yMin != null ? opts.yMin : -12;
    var yMax = opts.yMax != null ? opts.yMax : 12;
    var dpr = global.devicePixelRatio || 1;
    var w = canvas.clientWidth || 600;
    var h = canvas.clientHeight || 260;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    var g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    var padL = 42, padR = 14, padT = 14, padB = 26;
    var plotW = Math.max(10, w - padL - padR);
    var plotH = Math.max(10, h - padT - padB);
    var fMin = 20, fMax = 20000;
    function xOf(f) { return padL + (Math.log(f / fMin) / Math.log(fMax / fMin)) * plotW; }
    function yOf(db) { return padT + (1 - (db - yMin) / (yMax - yMin)) * plotH; }

    /* 网格与文字随主题切换 */
    var light = document.documentElement.getAttribute('data-theme') === 'light';
    var gridColor = light ? 'rgba(23,21,31,0.08)' : 'rgba(255,255,255,0.07)';
    var textColor = light ? 'rgba(23,21,31,0.45)' : 'rgba(255,255,255,0.42)';
    var zeroColor = light ? 'rgba(23,21,31,0.2)' : 'rgba(255,255,255,0.18)';

    g.lineWidth = 1;
    g.strokeStyle = gridColor;
    g.fillStyle = textColor;
    g.font = '11px system-ui, sans-serif';
    g.textAlign = 'center';
    [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].forEach(function (f) {
      var x = xOf(f);
      g.beginPath(); g.moveTo(x, padT); g.lineTo(x, padT + plotH); g.stroke();
      var label = f >= 1000 ? (f / 1000) + 'k' : String(f);
      g.fillText(label, x, h - 8);
    });
    g.textAlign = 'right';
    [yMin, -6, 0, 6, yMax].forEach(function (db) {
      if (db < yMin || db > yMax) return;
      var y = yOf(db);
      g.beginPath(); g.moveTo(padL, y); g.lineTo(padL + plotW, y); g.stroke();
      g.fillText((db > 0 ? '+' : '') + db, padL - 6, y + 4);
    });
    /* 0 dB 基线 */
    g.strokeStyle = zeroColor;
    g.beginPath(); g.moveTo(padL, yOf(0)); g.lineTo(padL + plotW, yOf(0)); g.stroke();

    /* 曲线 */
    series.forEach(function (s) {
      if (!s || !s.curve) return;
      g.beginPath();
      g.lineWidth = s.width || 2;
      g.strokeStyle = s.color || '#a78bfa';
      g.setLineDash(s.dash || []);
      var steps = 240;
      for (var i = 0; i <= steps; i++) {
        var f = fMin * Math.pow(fMax / fMin, i / steps);
        var x = xOf(f);
        var y = yOf(clamp(curveResponseDb(s.curve, f, false), yMin, yMax));
        if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
      }
      g.stroke();
      g.setLineDash([]);
    });
  }

  function downloadJSON(obj, filename) {
    var blob = new Blob([JSON.stringify(obj, null, 4)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(url);
      if (a.parentNode) a.parentNode.removeChild(a);
    }, 500);
  }

  /* localStorage 包装 */
  var store = {
    get: function (key, fallback) {
      try {
        var raw = global.localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (e) { return fallback; }
    },
    set: function (key, value) {
      try { global.localStorage.setItem(key, JSON.stringify(value)); return true; }
      catch (e) { return false; }
    },
    remove: function (key) {
      try { global.localStorage.removeItem(key); } catch (e) {}
    }
  };

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  global.EQ = {
    BANDS: BANDS,
    MIN_GAIN: MIN_GAIN,
    MAX_GAIN: MAX_GAIN,
    CURVE_MUSIC: CURVE_MUSIC,
    CURVE_MOVIE: CURVE_MOVIE,
    CURVE_FINAL: CURVE_FINAL,
    clamp: clamp,
    round1: round1,
    mean: mean,
    shuffle: shuffle,
    cloneCurve: cloneCurve,
    flatCurve: flatCurve,
    makeCurve: makeCurve,
    toDriverJSON: toDriverJSON,
    fromDriverJSON: fromDriverJSON,
    peakingResponseDb: peakingResponseDb,
    curveResponseDb: curveResponseDb,
    cssVar: cssVar,
    drawCurve: drawCurve,
    downloadJSON: downloadJSON,
    store: store
  };
})(window);
