export const MAX_STEPS = 200_000;

export function validate({kind, target, epsilon, a, b, p}) {
  if (!['wave', 'harmonic', 'leibniz', 'sine'].includes(kind) ||
      ![target, epsilon, a].every(Number.isFinite)) throw new Error('Введите конечные числа.');
  if (epsilon <= 0) throw new Error('Точность ε должна быть больше нуля.');
  if (epsilon < 10 * Number.EPSILON * Math.max(1, Math.abs(target)))
    throw new Error('ε слишком мало для выбранного L.');
  if (kind === 'wave') {
    if (![b, p, a + Math.abs(b)].every(Number.isFinite)) throw new Error('Введите конечные числа.');
    if (a <= Math.abs(b) || p <= 0 || p > 1) throw new Error('Нужны A > |B| и 0 < p ≤ 1.');
  } else if (a <= 0) throw new Error('Коэффициент C должен быть больше нуля.');
}

export function term(n, v) {
  if (v.kind === 'sine') return v.a * Math.sin(n) / n;
  const sign = n % 2 ? 1 : -1;
  if (v.kind === 'harmonic') return sign * v.a / n;
  if (v.kind === 'leibniz') return sign * v.a / (2 * n - 1);
  return sign * (v.a + v.b * Math.sin(n)) / n ** v.p;
}

export function bound(n, v) {
  if (v.kind === 'wave') return (v.a + Math.abs(v.b)) / n ** v.p;
  if (v.kind === 'leibniz') return v.a / (2 * n - 1);
  return v.a / n;
}

function nextIndex(n, sign, v) {
  if (v.kind !== 'sine') return n % 2 === (sign > 0 ? 1 : 0) ? n : n + 1;
  while (term(n, v) * sign <= 0) n++;
  return n;
}

export function calculate(v, limit = MAX_STEPS) {
  validate(v);
  const original = [0], rearranged = [0];
  let positive = nextIndex(1, 1, v), negative = nextIndex(1, -1, v);
  const stable = () => Math.abs(rearranged.at(-1) - v.target) <= v.epsilon &&
    bound(positive, v) <= v.epsilon && bound(negative, v) <= v.epsilon;
  if (stable()) return {original, rearranged, stableStep: 0};

  for (let k = 1; k <= limit; k++) {
    original.push(original.at(-1) + term(k, v));
    let value;
    if (rearranged.at(-1) <= v.target) {
      value = term(positive, v);
      positive = nextIndex(positive + 1, 1, v);
    } else {
      value = term(negative, v);
      negative = nextIndex(negative + 1, -1, v);
    }
    rearranged.push(rearranged.at(-1) + value);
    if (stable()) return {original, rearranged, stableStep: k};
  }
  return {original, rearranged, stableStep: null};
}

export function roughSteps(v) {
  const absTarget = Math.abs(v.target);
  if (v.kind === 'wave') {
    const bySize = ((v.a + Math.abs(v.b)) / v.epsilon) ** (1 / v.p);
    const byTarget = v.p < .99
      ? Math.max(1, absTarget * (1 - v.p) * 2 ** v.p / v.a) ** (1 / (1 - v.p))
      : Math.exp(2 * absTarget / v.a);
    return Math.max(bySize, byTarget);
  }
  return Math.max(v.a / v.epsilon,
    Math.exp(({harmonic: 2, leibniz: 4, sine: Math.PI})[v.kind] * absTarget / v.a));
}
