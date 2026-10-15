import assert from 'node:assert/strict';
import {calculate, term} from './series.js';

for (const [kind, expected] of [['wave', 489], ['harmonic', 127], ['leibniz', 560], ['sine', 177]]) {
  const v = {kind, target: 2, epsilon: .05, a: kind === 'wave' ? 1.5 : 1, b: .5, p: .6};
  const result = calculate(v);
  assert.equal(result.stableStep, expected);
  for (let k = 1; k < result.original.length; k++)
    assert.ok(Math.abs(result.original[k] - result.original[k - 1] - term(k, v)) < 1e-12);
  assert.ok(Math.abs(result.rearranged.at(-1) - v.target) <= v.epsilon);
}

assert.throws(() => calculate({kind: 'wave', target: 2, epsilon: .05, a: .4, b: .5, p: .6}));
for (const kind of ['wave', 'sine']) {
  const v = {kind, target: -1, epsilon: .08, a: 1.2, b: -.3, p: .75};
  const result = calculate(v);
  assert.ok(result.stableStep !== null);
  assert.ok(Math.abs(result.rearranged.at(-1) - v.target) <= v.epsilon);
}
console.log('Four browser series checks passed.');
