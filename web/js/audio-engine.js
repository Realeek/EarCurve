/* audio-engine.js — Web Audio 封装：纯音、解码、离线渲染、A/B 同步播放（无依赖） */
(function (global) {
  'use strict';

  var ctx = null;
  var pair = null;
  var tone = null;
  /* 测试音基础幅度：0.8 ≈ -1.9 dBFS。
     部分 2.4G 接收器在约 -66 dBFS 处有静音门限；幅度越高，门限对应的滑块档位越低。 */
  var TONE_AMPLITUDE = 0.8;

  function dbToGain(db) { return Math.pow(10, db / 20); }

  function ensureContext() {
    if (ctx) {
      if (ctx.state === 'suspended') ctx.resume();
      return Promise.resolve(ctx);
    }
    var AC = global.AudioContext || global.webkitAudioContext;
    if (!AC) return Promise.reject(new Error('当前环境不支持音频播放，请更换支持 Web Audio 的运行环境'));
    ctx = new AC({ latencyHint: 'interactive' });
    if (ctx.state === 'suspended') ctx.resume();
    return Promise.resolve(ctx);
  }

  function getContext() { return ctx; }

  function listOutputs() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return Promise.resolve([]);
    return navigator.mediaDevices.enumerateDevices().then(function (devices) {
      return devices.filter(function (d) { return d.kind === 'audiooutput'; });
    }).catch(function () { return []; });
  }

  function setOutputDevice(deviceId) {
    return ensureContext().then(function (c) {
      if (typeof c.setSinkId !== 'function') return false;
      return c.setSinkId(deviceId || '').then(function () { return true; }).catch(function () { return false; });
    });
  }

  /* ---------- 纯音 ---------- */

  var burstCache = {};
  var BURST_ON = 0.2;
  var BURST_OFF = 0.2;

  /* 短促纯音循环：BURST_ON 发声 + BURST_OFF 静音，循环播放 */
  function burstBuffer(c, freq) {
    var key = freq + '@' + c.sampleRate + '@' + BURST_ON + '@' + BURST_OFF;
    if (burstCache[key]) return burstCache[key];
    var sr = c.sampleRate;
    var onSec = BURST_ON;
    var offSec = BURST_OFF;
    var len = Math.round((onSec + offSec) * sr);
    var nOn = Math.round(onSec * sr);
    var fade = Math.max(1, Math.round(0.015 * sr));
    var buf = c.createBuffer(1, len, sr);
    var d = buf.getChannelData(0);
    var w = 2 * Math.PI * freq / sr;
    for (var i = 0; i < nOn; i++) {
      var env = 1;
      if (i < fade) env = i / fade;
      else if (i > nOn - fade) env = Math.max(0, (nOn - i) / fade);
      d[i] = Math.sin(w * i) * env;
    }
    burstCache[key] = buf;
    return buf;
  }

  /* opts.mode: 'burst'（默认，短促循环）| 'steady'（连续音，用于校准音量） */
  function startTone(freq, ear, levelDb, opts) {
    var mode = (opts && opts.mode === 'steady') ? 'steady' : 'burst';
    return ensureContext().then(function (c) {
      stopTone();
      var env = c.createGain();
      var pan = c.createStereoPanner();
      pan.pan.value = (ear === 'L' ? -1 : ear === 'R' ? 1 : 0);
      env.gain.value = 0;
      env.connect(pan);
      pan.connect(c.destination);
      var src;
      if (mode === 'steady') {
        src = c.createOscillator();
        src.type = 'sine';
        src.frequency.value = freq;
      } else {
        src = c.createBufferSource();
        src.buffer = burstBuffer(c, freq);
        src.loop = true;
      }
      src.connect(env);
      var t = c.currentTime;
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(dbToGain(levelDb) * TONE_AMPLITUDE, t + 0.03);
      src.start(t);
      tone = { src: src, env: env, pan: pan, levelDb: levelDb, freq: freq, ear: ear, mode: mode };
      return tone;
    });
  }

  function setToneLevel(levelDb) {
    if (!tone || !ctx) return;
    var t = ctx.currentTime;
    tone.levelDb = levelDb;
    holdParam(tone.env.gain, t);
    tone.env.gain.linearRampToValueAtTime(dbToGain(levelDb) * TONE_AMPLITUDE, t + 0.03);
  }

  function stopTone() {
    if (!tone || !ctx) { tone = null; return; }
    var t = ctx.currentTime;
    var env = tone.env;
    var src = tone.src;
    holdParam(env.gain, t);
    env.gain.linearRampToValueAtTime(0, t + 0.04);
    try { src.stop(t + 0.06); } catch (e) {}
    tone = null;
  }

  function isTonePlaying() { return !!tone; }

  function holdParam(param, time) {
    if (typeof param.cancelAndHoldAtTime === 'function') {
      param.cancelAndHoldAtTime(time);
    } else {
      param.cancelScheduledValues(time);
      param.setValueAtTime(param.value, time);
    }
  }

  /* ---------- 文件解码 / 片段 ---------- */

  function decodeFile(file) {
    return ensureContext().then(function (c) {
      return file.arrayBuffer().then(function (ab) {
        return new Promise(function (resolve, reject) {
          var p = c.decodeAudioData(ab, resolve, reject);
          if (p && typeof p.then === 'function') p.then(resolve, reject);
        });
      });
    });
  }

  /* 从曲目中段截取一段，返回新的 AudioBuffer */
  function sliceExcerpt(buffer, seconds) {
    return ensureContext().then(function (c) {
      var sr = buffer.sampleRate;
      var len = Math.min(buffer.length, Math.floor(seconds * sr));
      var maxStart = Math.max(0, buffer.length - len);
      var start = Math.floor(Math.min(maxStart, buffer.length * 0.3 + Math.random() * Math.max(0, buffer.length * 0.4 - len)));
      if (start < 0) start = 0;
      var out = c.createBuffer(buffer.numberOfChannels, len, sr);
      for (var ch = 0; ch < buffer.numberOfChannels; ch++) {
        out.copyToChannel(buffer.getChannelData(ch).subarray(start, start + len), ch);
      }
      return out;
    });
  }

  function rmsOf(buffer) {
    var sum = 0, n = 0;
    for (var ch = 0; ch < buffer.numberOfChannels; ch++) {
      var d = buffer.getChannelData(ch);
      for (var i = 0; i < d.length; i++) { sum += d[i] * d[i]; n++; }
    }
    return Math.sqrt(sum / Math.max(1, n));
  }

  function peakOf(buffer) {
    var peak = 0;
    for (var ch = 0; ch < buffer.numberOfChannels; ch++) {
      var d = buffer.getChannelData(ch);
      for (var i = 0; i < d.length; i++) {
        var v = Math.abs(d[i]);
        if (v > peak) peak = v;
      }
    }
    return peak;
  }

  /* ---------- 离线渲染：片段 + 10 段 peaking 链 ---------- */

  function renderVariant(buffer, curve, startSec, durationSec) {
    return ensureContext().then(function () {
      var sr = buffer.sampleRate;
      var dur = Math.max(0.5, Math.min(durationSec, buffer.duration - startSec));
      var len = Math.ceil(dur * sr);
      var off = new OfflineAudioContext(2, len, sr);
      var src = off.createBufferSource();
      src.buffer = buffer;
      var node = src;
      curve.bands.forEach(function (b) {
        var f = off.createBiquadFilter();
        f.type = 'peaking';
        f.frequency.value = Math.min(b.freq, sr / 2 - 1);
        f.Q.value = b.q;
        f.gain.value = b.gain;
        node.connect(f);
        node = f;
      });
      var pre = off.createGain();
      var preGain = dbToGain(Number(curve.mainGain) || 0);
      var fade = 0.025;
      pre.gain.setValueAtTime(0, 0);
      pre.gain.linearRampToValueAtTime(preGain, fade);
      if (dur > fade * 2) {
        pre.gain.setValueAtTime(preGain, dur - fade);
        pre.gain.linearRampToValueAtTime(0, dur);
      }
      node.connect(pre);
      pre.connect(off.destination);
      src.start(0, startSec, dur);
      return off.startRendering();
    });
  }

  /* ---------- A/B 同步播放：两条 buffer 同时启动，仅切换增益 ---------- */

  function playPair(buf1, gain1, buf2, gain2) {
    return ensureContext().then(function (c) {
      stopPair();
      var s1 = c.createBufferSource();
      var s2 = c.createBufferSource();
      var g1 = c.createGain();
      var g2 = c.createGain();
      s1.buffer = buf1;
      s2.buffer = buf2;
      s1.connect(g1); g1.connect(c.destination);
      s2.connect(g2); g2.connect(c.destination);
      var t0 = c.currentTime + 0.08;
      var fade = 0.03;
      g1.gain.setValueAtTime(0, t0);
      g2.gain.setValueAtTime(0, t0);
      g1.gain.linearRampToValueAtTime(gain1, t0 + fade);
      s1.start(t0);
      s2.start(t0);
      pair = { s1: s1, s2: s2, g1: g1, g2: g2, gains: [gain1, gain2], active: 1, c: c };
      s1.addEventListener('ended', function () {
        if (pair && pair.s1 === s1) pair = null;
      });
      return {
        switchTo: function (which) { switchPair(which); },
        stop: stopPair,
        isActive: function () { return !!pair; }
      };
    });
  }

  function switchPair(which) {
    if (!pair) return;
    var now = pair.c.currentTime;
    var targets = [which === 1 ? pair.gains[0] : 0, which === 2 ? pair.gains[1] : 0];
    [pair.g1, pair.g2].forEach(function (g, i) {
      holdParam(g.gain, now);
      g.gain.linearRampToValueAtTime(targets[i], now + 0.03);
    });
    pair.active = which;
  }

  function stopPair() {
    if (!pair) return;
    var p = pair;
    pair = null;
    var now = p.c.currentTime;
    [p.g1, p.g2].forEach(function (g) {
      holdParam(g.gain, now);
      g.gain.linearRampToValueAtTime(0, now + 0.03);
    });
    [p.s1, p.s2].forEach(function (s) {
      try { s.stop(now + 0.06); } catch (e) {}
    });
  }

  function isPairPlaying() { return !!pair; }

  global.AudioEngine = {
    ensureContext: ensureContext,
    getContext: getContext,
    listOutputs: listOutputs,
    setOutputDevice: setOutputDevice,
    startTone: startTone,
    setToneLevel: setToneLevel,
    stopTone: stopTone,
    isTonePlaying: isTonePlaying,
    decodeFile: decodeFile,
    sliceExcerpt: sliceExcerpt,
    rmsOf: rmsOf,
    peakOf: peakOf,
    renderVariant: renderVariant,
    playPair: playPair,
    stopPair: stopPair,
    isPairPlaying: isPairPlaying
  };
})(window);
