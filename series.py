"""Conditional series and a constructive Riemann rearrangement."""

from dataclasses import dataclass
from math import exp, isfinite, pi, sin, ulp


MAX_STEPS = 200_000
KINDS = ("wave", "harmonic", "leibniz", "sine")


@dataclass(frozen=True)
class Parameters:
    target: float
    epsilon: float
    a: float
    b: float = 0
    p: float = 1
    kind: str = "wave"

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise ValueError("Неизвестный ряд.")
        if not all(isfinite(x) for x in (self.target, self.epsilon, self.a)):
            raise ValueError("Введите конечные числа.")
        if self.epsilon <= 0:
            raise ValueError("Точность ε должна быть больше нуля.")
        if self.epsilon < 10 * ulp(self.target):
            raise ValueError("ε слишком мало для выбранного L.")
        if self.kind == "wave":
            if not isfinite(self.b) or not isfinite(self.p):
                raise ValueError("Введите конечные числа.")
            if not isfinite(self.a + abs(self.b)):
                raise ValueError("Коэффициенты слишком велики.")
            if self.a <= abs(self.b) or not 0 < self.p <= 1:
                raise ValueError("Нужны A > |B| и 0 < p ≤ 1.")
        elif self.a <= 0:
            raise ValueError("Коэффициент C должен быть больше нуля.")


@dataclass
class Result:
    rearranged: list[float]
    original: list[float]
    stable_step: int | None


def term(n: int, params: Parameters) -> float:
    if params.kind == "wave":
        return (1 if n % 2 else -1) * (params.a + params.b * sin(n)) / n**params.p
    if params.kind == "harmonic":
        return (1 if n % 2 else -1) * params.a / n
    if params.kind == "leibniz":
        return (1 if n % 2 else -1) * params.a / (2 * n - 1)
    return params.a * sin(n) / n


def bound(n: int, params: Parameters) -> float:
    """Decreasing upper bound for the absolute value of every later term."""
    if params.kind == "wave":
        return (params.a + abs(params.b)) / n**params.p
    if params.kind == "leibniz":
        return params.a / (2 * n - 1)
    return params.a / n


def next_index(start: int, sign: int, params: Parameters) -> int:
    if params.kind != "sine":
        parity = 1 if sign > 0 else 0
        return start if start % 2 == parity else start + 1
    while term(start, params) * sign <= 0:
        start += 1
    return start


def calculate(params: Parameters, limit: int = MAX_STEPS) -> Result:
    params.validate()
    rearranged = [0.0]
    original = [0.0]
    positive = next_index(1, 1, params)
    negative = next_index(1, -1, params)

    def stable() -> bool:
        return (abs(rearranged[-1] - params.target) <= params.epsilon
                and bound(positive, params) <= params.epsilon
                and bound(negative, params) <= params.epsilon)

    if stable():
        return Result(rearranged, original, 0)

    for k in range(1, limit + 1):
        original.append(original[-1] + term(k, params))
        if rearranged[-1] <= params.target:
            value = term(positive, params)
            positive = next_index(positive + 1, 1, params)
        else:
            value = term(negative, params)
            negative = next_index(negative + 1, -1, params)
        rearranged.append(rearranged[-1] + value)
        if stable():
            return Result(rearranged, original, k)

    return Result(rearranged, original, None)


def rough_steps(params: Parameters) -> float:
    """Order-of-magnitude estimate when the exact run exceeds MAX_STEPS."""
    params.validate()
    try:
        if params.kind == "wave":
            by_term_size = ((params.a + abs(params.b)) / params.epsilon) ** (1 / params.p)
            if params.p < 0.99:
                by_target = max(1.0, abs(params.target) * (1 - params.p) * 2**params.p / params.a) ** (1 / (1 - params.p))
            else:
                by_target = exp(2 * abs(params.target) / params.a)
        else:
            by_term_size = params.a / params.epsilon
            slope = {"harmonic": 2, "leibniz": 4, "sine": pi}[params.kind]
            by_target = exp(slope * abs(params.target) / params.a)
        return max(by_term_size, by_target)
    except OverflowError:
        return float("inf")
