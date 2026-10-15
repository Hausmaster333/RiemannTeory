import {MAX_STEPS, calculate, roughSteps} from './series.js';

const el = id => document.getElementById(id);
const fields = ['target', 'epsilon', 'a', 'b', 'p'];
const dialog = el('seriesDialog');
const canvas = el('chart');
const presets = {
  wave: ['1,5', '0,5', '0,6'],
  harmonic: ['1', '0', '1'],
  leibniz: ['1', '0', '1'],
  sine: ['1', '0', '1']
};
let kind = 'wave', params = null, result = null, step = 0, timer = null, debounce = null;
let view = new URLSearchParams(location.search).get('view') === 'center' ? 'center' : 'history';
let centeredSpan = 1, animateCenter = false;

function read(id) {
  const text = el(id).value.trim().replace(',', '.');
  if (!text) throw new Error('Введите числа во все поля.');
  return Number(text);
}

function values() {
  const v = {kind, target: read('target'), epsilon: read('epsilon'), a: read('a'), b: 0, p: 1};
  if (kind === 'wave') { v.b = read('b'); v.p = read('p'); }
  return v;
}

function stop() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  el('play').textContent = 'Воспроизвести';
}

function countText(n, approximate = false) {
  if (!Number.isFinite(n)) return 'очень много';
  const prefix = approximate ? '≈ ' : '';
  if (n >= 1e9) return prefix + (n / 1e9).toFixed(1).replace('.', ',') + ' млрд';
  if (n >= 1e6) return prefix + (n / 1e6).toFixed(1).replace('.', ',') + ' млн';
  if (approximate && n >= 1e4) return prefix + (n / 1e3).toFixed(1).replace('.', ',') + ' тыс.';
  return prefix + Math.round(n).toLocaleString('ru-RU');
}

function decimal(x, digits) {
  if (x && Math.abs(x) < 10 ** -digits) return x.toExponential(2).replace('.', ',');
  const s = x.toFixed(digits);
  return (Number(s) === 0 ? s.replace('-', '') : s).replace('.', ',');
}

function latexNumber(x) {
  const s = Number(x.toPrecision(5)).toString();
  if (!s.includes('e')) return s;
  const parts = s.split('e');
  return parts[0] + '\\cdot10^{' + Number(parts[1]) + '}';
}

function formula(v) {
  const amount = latexNumber(v.a);
  const prefix = '\\sum_{n=1}^{\\infty}';
  if (v.kind === 'harmonic') return prefix + '(-1)^{n+1}\\frac{' + amount + '}{n}';
  if (v.kind === 'leibniz') return prefix + '(-1)^{n+1}\\frac{' + amount + '}{2n-1}';
  if (v.kind === 'sine') return prefix + '\\frac{' + (v.a === 1 ? '' : amount) + '\\sin n}{n}';
  const sign = v.b > 0 ? '+' : '-';
  const numerator = amount + (v.b ? sign + latexNumber(Math.abs(v.b)) + '\\sin n' : '');
  return prefix + '(-1)^{n+1}\\frac{' + numerator + '}{n^{' + latexNumber(v.p) + '}}';
}

function updateFormula(v) {
  const target = el('formula');
  if (window.MathJax?.typesetClear) window.MathJax.typesetClear([target]);
  target.textContent = '\\(' + formula(v) + '\\)';
  if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([target]).catch(() => {});
}

function recompute() {
  debounce = null;
  stop();
  animateCenter = false;
  try {
    params = values();
    result = calculate(params);
    el('validation').textContent = kind === 'wave' ? 'A > |B| · 0 < p ≤ 1' : 'C > 0';
    el('validation').classList.remove('error');
  } catch (error) {
    params = result = null;
    el('validation').textContent = error.message || 'Проверьте значения.';
    el('validation').classList.add('error');
    el('estimate').textContent = '—';
    el('estimateNote').textContent = '';
    for (const id of ['sum', 'error', 'count']) el(id).textContent = '—';
    draw();
    return;
  }
  step = 0;
  centeredSpan = params.epsilon * 4;
  for (let i = 0; i < result.rearranged.length; i++)
    centeredSpan = Math.max(centeredSpan, Math.abs(result.rearranged[i] - params.target),
      Math.abs(result.original[i] - params.target));
  centeredSpan *= 1.12;
  el('position').max = Math.max(1, result.rearranged.length - 1);
  el('position').value = 0;
  if (result.stableStep === null) {
    el('estimate').textContent = countText(Math.max(MAX_STEPS + 1, roughSteps(params)), true);
    el('estimateNote').textContent = 'Оценка; показ до ' + countText(MAX_STEPS) + ' шагов.';
  } else {
    el('estimate').textContent = countText(result.stableStep);
    el('estimateNote').textContent = 'До устойчивого приближения.';
  }
  updateFormula(params);
  updateStep();
}

function schedule() {
  if (debounce !== null) clearTimeout(debounce);
  debounce = setTimeout(recompute, 350);
}

function selectPreset(next) {
  presets[kind] = ['a', 'b', 'p'].map(id => el(id).value);
  kind = next;
  ['a', 'b', 'p'].forEach((id, i) => { el(id).value = presets[kind][i]; });
  el('aLabel').textContent = kind === 'wave' ? 'Коэффициент A' : 'Коэффициент C';
  el('bField').hidden = el('pField').hidden = kind !== 'wave';
  document.querySelectorAll('.preset').forEach(button =>
    button.classList.toggle('active', button.dataset.kind === kind));
  dialog.close();
  if (debounce !== null) clearTimeout(debounce);
  recompute();
}

function draw() {
  if (view === 'center') {
    el('centerStage').style.visibility = result && params ? 'visible' : 'hidden';
    if (result && params) drawCentered();
    return;
  }
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  const g = canvas.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, width, height);
  if (!result || !params) return;

  const left = width < 500 ? 43 : 52, right = 13, top = 12, bottom = 33;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - top - bottom);
  const zoom = el('zoom').checked;
  const first = zoom ? Math.max(0, step - 180) : 0;
  const last = Math.max(first + 20, step + 2);
  const stride = Math.max(1, Math.floor((step - first) / 900));
  const indices = [];
  for (let i = first; i <= step; i += stride) indices.push(i);
  if (indices.at(-1) !== step) indices.push(step);
  const ys = indices.map(i => result.rearranged[i]).concat(params.target);
  if (!zoom) ys.push(...indices.map(i => result.original[i]));
  const low = Math.min(...ys), high = Math.max(...ys);
  const pad = Math.max(params.epsilon * 4, (high - low) * .12, .05);
  const minY = low - pad, maxY = high + pad;
  const x = i => left + (i - first) / (last - first) * plotWidth;
  const y = value => top + (maxY - value) / (maxY - minY) * plotHeight;

  g.fillStyle = '#eaf2f6';
  const bandTop = Math.max(top, y(params.target + params.epsilon));
  const bandBottom = Math.min(top + plotHeight, y(params.target - params.epsilon));
  if (bandBottom > bandTop) g.fillRect(left, bandTop, plotWidth, bandBottom - bandTop);

  g.font = '12px "Segoe UI",Arial,sans-serif';
  g.lineWidth = 1;
  g.textAlign = 'right';
  g.textBaseline = 'middle';
  const tickDigits = Math.min(6, Math.max(1, Math.ceil(-Math.log10((maxY - minY) / 4)) + 1));
  for (let i = 0; i <= 4; i++) {
    const value = minY + (maxY - minY) * i / 4;
    const yy = y(value);
    g.strokeStyle = '#edf0f1';
    g.beginPath(); g.moveTo(left, yy); g.lineTo(left + plotWidth, yy); g.stroke();
    g.fillStyle = '#68737d';
    g.fillText(decimal(value, tickDigits), left - 8, yy);
  }
  g.strokeStyle = '#dee3e6';
  g.beginPath(); g.moveTo(left, top); g.lineTo(left, top + plotHeight);
  g.lineTo(left + plotWidth, top + plotHeight); g.stroke();
  g.textAlign = 'center'; g.textBaseline = 'top'; g.fillStyle = '#68737d';
  for (let i = 0; i <= 4; i++) {
    const value = first + (last - first) * i / 4;
    g.fillText(String(Math.round(value)), x(value), top + plotHeight + 7);
  }
  g.save(); g.translate(12, top + plotHeight / 2); g.rotate(-Math.PI / 2);
  g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('Сумма', 0, 0); g.restore();

  g.strokeStyle = '#346581'; g.lineWidth = 1.4; g.setLineDash([6, 5]);
  g.beginPath(); g.moveTo(left, y(params.target)); g.lineTo(left + plotWidth, y(params.target)); g.stroke();
  g.setLineDash([]);
  function line(series, color, lineWidth) {
    g.strokeStyle = color; g.lineWidth = lineWidth; g.beginPath();
    indices.forEach((i, j) => j ? g.lineTo(x(i), y(series[i])) : g.moveTo(x(i), y(series[i])));
    g.stroke();
  }
  if (!zoom) line(result.original, '#a9b3b9', 1.5);
  line(result.rearranged, '#1f2933', 2);
  g.fillStyle = '#346581'; g.strokeStyle = '#fff'; g.lineWidth = 2;
  g.beginPath(); g.arc(x(step), y(result.rearranged[step]), 4.5, 0, Math.PI * 2);
  g.fill(); g.stroke();
}

function drawCentered() {
  const span = el('zoom').checked ? params.epsilon * 8 : centeredSpan;
  const percent = value => 50 + (value - params.target) / span * 50;
  const digits = Math.min(14, Math.max(3, Math.ceil(-Math.log10(params.epsilon)) + 2));
  const tickDigits = Math.min(14, Math.max(0, Math.ceil(-Math.log10(span / 2)) + 1));
  const formatTick = value => Number(value.toFixed(tickDigits)).toLocaleString('ru-RU', {maximumFractionDigits: tickDigits});
  el('targetLabel').textContent = 'L = ' + params.target.toLocaleString('ru-RU', {maximumSignificantDigits: 15});
  el('toleranceBand').style.width = Math.min(100, params.epsilon / span * 100) + '%';
  el('toleranceBand').title = 'Допуск ± ε = ' + params.epsilon.toLocaleString('ru-RU', {maximumSignificantDigits: 6});
  [...el('centerTicks').children].forEach((tick, i) => {
    tick.textContent = i === 2 ? 'L' : formatTick(params.target + span * (i / 2 - 1));
  });
  for (const [id, value] of [['originalMarker', result.original[step]], ['arrangedMarker', result.rearranged[step]]]) {
    const marker = el(id), raw = percent(value), position = Math.max(0, Math.min(100, raw));
    marker.style.transition = animateCenter ? '' : 'none';
    marker.style.left = position + '%';
    marker.classList.toggle('outside', raw < 0 || raw > 100);
    marker.classList.toggle('at-left', position < 10);
    marker.classList.toggle('at-right', position > 90);
    marker.querySelector('.point').textContent = raw < 0 ? '‹' : raw > 100 ? '›' : '';
    marker.querySelector('.marker-value').textContent = decimal(value, digits);
  }
  const position = Math.max(0, Math.min(100, percent(result.rearranged[step])));
  el('distanceLine').style.transition = animateCenter ? '' : 'none';
  el('distanceLine').style.left = Math.min(50, position) + '%';
  el('distanceLine').style.width = Math.abs(position - 50) + '%';
  const trail = document.createDocumentFragment();
  const first = Math.max(0, step - 10);
  for (let i = first; i < step; i++) {
    const position = percent(result.rearranged[i]);
    if (position < 0 || position > 100) continue;
    const dot = document.createElement('i');
    dot.style.left = position + '%';
    dot.style.opacity = .08 + .3 * (i - first) / Math.max(1, step - first);
    trail.append(dot);
  }
  el('sumTrail').replaceChildren(trail);
}

function setView(next, updateUrl = true) {
  stop();
  view = next;
  animateCenter = false;
  const centered = view === 'center';
  canvas.hidden = centered;
  el('centerStage').hidden = !centered;
  el('viewLegend').hidden = centered;
  el('historyView').setAttribute('aria-pressed', String(!centered));
  el('centerView').setAttribute('aria-pressed', String(centered));
  el('visualTitle').textContent = centered ? 'Приближение к L' : 'Частичные суммы';
  el('axisCaption').textContent = centered ? 'Значение частичной суммы Sₖ' : 'Число членов k';
  if (updateUrl) {
    const url = new URL(location.href);
    if (centered) url.searchParams.set('view', 'center');
    else url.searchParams.delete('view');
    history.replaceState(null, '', url);
  }
  draw();
}

function updateStep() {
  if (!result || !params) return;
  el('position').value = step;
  const digits = Math.min(14, Math.max(3, Math.ceil(-Math.log10(params.epsilon)) + 2));
  el('sum').textContent = decimal(result.rearranged[step], digits);
  el('error').textContent = decimal(Math.abs(result.rearranged[step] - params.target), digits);
  el('count').textContent = countText(step);
  canvas.setAttribute('aria-label', 'Частичные суммы: шаг ' + step + ', сумма ' + el('sum').textContent);
  el('centerStage').setAttribute('aria-label', 'Цель L = ' + params.target + ', шаг ' + step + ', сумма ' + el('sum').textContent);
  draw();
}

function moveTo(n, animate = false) {
  if (!result) return;
  animateCenter = animate && view === 'center';
  step = Math.max(0, Math.min(result.rearranged.length - 1, n));
  updateStep();
}

el('seriesButton').addEventListener('click', () => { stop(); dialog.showModal(); });
el('closeDialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
document.querySelectorAll('.preset').forEach(button =>
  button.addEventListener('click', () => selectPreset(button.dataset.kind)));
fields.forEach(id => el(id).addEventListener('input', schedule));
el('historyView').addEventListener('click', () => setView('history'));
el('centerView').addEventListener('click', () => setView('center'));
el('zoom').addEventListener('change', () => { animateCenter = false; draw(); });
el('position').addEventListener('input', event => { stop(); moveTo(Number(event.target.value)); });
el('step').addEventListener('click', () => { stop(); if (result) moveTo(step + 1, true); });
el('reset').addEventListener('click', () => { stop(); if (result) moveTo(0); });
el('play').addEventListener('click', () => {
  if (timer !== null) { stop(); return; }
  if (!result) return;
  if (step >= result.rearranged.length - 1) moveTo(0);
  el('play').textContent = 'Пауза';
  const tick = () => {
    const increment = Number.parseInt(el('speed').value, 10);
    moveTo(step + increment, true);
    if (step >= result.rearranged.length - 1) stop();
  };
  tick();
  if (timer === null && step < result.rearranged.length - 1) timer = setInterval(tick, view === 'center' ? 400 : 55);
});
new ResizeObserver(draw).observe(canvas.parentElement);
document.querySelector('[data-kind="wave"]').classList.add('active');
setView(view, false);
recompute();
window.addEventListener('load', () => {
  if (window.MathJax?.typesetPromise)
    window.MathJax.typesetPromise([...document.querySelectorAll('.preset-formula'), el('formula')]).catch(() => {});
});
