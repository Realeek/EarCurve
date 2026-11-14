/* 纯逻辑测试：node test/eq.test.js（不依赖浏览器） */
global.window = {};
require('../web/js/eq.js');
const EQ = global.window.EQ;

let failures = 0;
function check(name, cond, extra) {
  if (cond) {
    console.log('PASS ' + name);
  } else {
    failures++;
    console.error('FAIL ' + name + (extra ? ' — ' + extra : ''));
  }
}
function near(a, b, eps) { return Math.abs(a - b) <= (eps == null ? 0.01 : eps); }

const flat = EQ.flatCurve('自定义1');
check('flatCurve 10 bands', flat.bands.length === 10, 'got ' + flat.bands.length);
check('flatCurve all zero', flat.bands.every(b => b.gain === 0 && b.q === 1));
check('flatCurve mainGain 0', flat.mainGain === 0);

const json = EQ.toDriverJSON(flat);
check('driver json keys', ['freq', 'q', 'sound', 'type', 'main_gain', 'name'].every(k => k in json));
check('freq sorted asc', json.freq.every((v, i) => i === 0 || parseFloat(json.freq[i - 1]) < parseFloat(v)));
check('freq count 10', json.freq.length === 10);
check('q strings 2dp', json.q.every(v => typeof v === 'string' && /^\d+\.\d{2}$/.test(v)));
check('sound strings', json.sound.every(v => typeof v === 'string'));
check('type all "1"', json.type.every(v => v === '1'));
check('main_gain number', typeof json.main_gain === 'number');
check('name kept', json.name === '自定义1');
check('curve names', EQ.CURVE_MUSIC === 'EarCurve-Music' && EQ.CURVE_MOVIE === 'EarCurve-Movie' && EQ.CURVE_FINAL === 'EarCurve-Final');

const sample = {
  freq: ['2900', '5328', '40', '100', '9000', '20', '200', '250', '140', '270'],
  q: ['2.50', '1.50', '1.00', '2.00', '4.00', '0.80', '2.00', '1.00', '1.00', '3.50'],
  sound: ['3', '-4', '-2', '-3.5', '-3', '-6', '3', '3.5', '1', '0'],
  type: ['1', '1', '1', '1', '1', '1', '1', '1', '1', '1'],
  main_gain: 0,
  name: '自定义1'
};
const parsed = EQ.fromDriverJSON(sample);
check('sample parse 10 bands', parsed.bands.length === 10);
check('sample gain lookup', parsed.bands.find(b => b.freq === 9000).gain === -3);
const back = EQ.toDriverJSON(parsed);
check('sample roundtrip freq', back.freq.join(',') === '20,40,100,140,200,250,270,2900,5328,9000', back.freq.join(','));
check('sample roundtrip gain 2900', back.sound[7] === '3', back.sound[7]);

check('0 dB peaking response is 0 dB', near(EQ.peakingResponseDb(1000, { freq: 1000, q: 1, gain: 0 }), 0, 1e-9));
check('+6 dB peaking at center ~= 6 dB', near(EQ.peakingResponseDb(1000, { freq: 1000, q: 1, gain: 6 }), 6, 0.01), String(EQ.peakingResponseDb(1000, { freq: 1000, q: 1, gain: 6 })));
check('-6 dB peaking at center ~= -6 dB', near(EQ.peakingResponseDb(1000, { freq: 1000, q: 1, gain: -6 }), -6, 0.01));
check('curve response flat = 0', near(EQ.curveResponseDb(flat, 500), 0, 1e-9));

const boosted = EQ.makeCurve('x', [0, 0, 0, 0, 0, 0, 20, 0, 0, 0], 0);
check('makeCurve clamps gain to +12', boosted.bands[6].gain === 12);
check('clamp', EQ.clamp(99, -12, 12) === 12 && EQ.clamp(-99, -12, 12) === -12);
check('round1', EQ.round1(3.14159) === 3.1 && EQ.round1(-0.04) === 0);

try { EQ.fromDriverJSON({}); check('invalid json throws', false); }
catch (e) { check('invalid json throws', true); }

console.log(failures ? failures + ' FAILURE(S)' : 'ALL PASS');
process.exitCode = failures ? 1 : 0;
