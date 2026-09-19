"""The arithmetic behind the funnel projection, kept apart from the reading of a record.

Split out of :mod:`.funnel_projection` for size; the two are one command. Every
function here is standard-library arithmetic with no notion of the study: exact
binomial intervals through the incomplete beta function, the beta-binomial
predictive, and the finite-population posterior, each computed so that the size
of the input does not overflow the float range.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

DEFAULT_CONFIDENCE = 0.95
#: The largest fresh discovery :func:`candidates_for_chance` will consider.
SEARCH_CAP = 100_000


class ProjectionInputError(ValueError):
    """An input is not the shape this projection knows how to read."""


# ---- exact arithmetic --------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """The continued fraction for the incomplete beta, by the modified Lentz method."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """The regularised incomplete beta function I_x(a, b)."""
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"x must be in [0, 1], got {x}")
    if x == 0.0 or x == 1.0:
        return x
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), through the exact beta identity.

    ``P(X <= k) = I_{1-p}(n - k, k + 1)``. Using the identity instead of a sum
    keeps the cost independent of ``n``, where summing ``math.comb`` terms
    overflows the float range once the binomial coefficients pass 1.8e308.
    """
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    return min(1.0, max(0.0, betainc(n - k, k + 1, 1.0 - p)))


def clopper_pearson(k: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> tuple[float, float]:
    """The exact two-sided interval on a binomial proportion.

    Lower bound: the largest p with P(X >= k | p) <= alpha/2; upper bound: the
    largest p with P(X <= k | p) >= alpha/2. Both are found by bisection on the
    exact tail, and at k = 0 and k = n they are the closed forms
    ``1 - (alpha/2)**(1/n)`` and ``(alpha/2)**(1/n)``.
    """
    if n <= 0 or k < 0 or k > n:
        raise ProjectionInputError(f"need 0 <= k <= n with n > 0, got k={k}, n={n}")
    if not 0.0 < confidence < 1.0:
        raise ProjectionInputError(f"confidence must be strictly between 0 and 1, got {confidence}")
    half = (1.0 - confidence) / 2.0

    def bisect(tail: Callable[[float], float], increasing: bool) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if (tail(mid) > half) == increasing:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2.0

    lower = 0.0 if k == 0 else bisect(lambda p: 1.0 - binomial_cdf(k - 1, n, p), increasing=True)
    upper = 1.0 if k == n else bisect(lambda p: binomial_cdf(k, n, p), increasing=False)
    return lower, upper


def _normalised(logs: Sequence[float]) -> list[float]:
    peak = max(logs)
    weights = [math.exp(v - peak) for v in logs]
    total = sum(weights)
    return [w / total for w in weights]


def beta_binomial_pmf(t: int, k: int, n: int) -> list[float]:
    """P(Y = y) for y in 0..t: evaluable among t fresh candidates after k of n.

    Uniform prior on the rate, so Y ~ BetaBinomial(t, k + 1, n - k + 1). Terms
    are computed in log space and renormalised, so the vector sums to one to
    floating precision at any size.
    """
    if t < 0 or n < 0 or k < 0 or k > n:
        raise ProjectionInputError(f"need t >= 0 and 0 <= k <= n, got t={t}, k={k}, n={n}")
    a, b = k + 1, n - k + 1
    base = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) - math.lgamma(a + b + t)
    return _normalised([
        math.lgamma(t + 1) - math.lgamma(y + 1) - math.lgamma(t - y + 1)
        + math.lgamma(y + a) + math.lgamma(t - y + b) + base
        for y in range(t + 1)
    ])


def hypergeometric_posterior(n_seen: int, k_seen: int, population: int) -> list[float]:
    """P(K = j) for j in 0..population: evaluable in a population sampled at random.

    The sample of ``n_seen`` judged ``k_seen`` evaluable; with a uniform prior
    over K the posterior is the hypergeometric likelihood renormalised. Terms
    are computed in log space, so a large population does not overflow.
    """
    if not 0 <= k_seen <= n_seen <= population:
        raise ProjectionInputError(f"need 0 <= k <= n <= N, got k={k_seen}, n={n_seen}, N={population}")
    logs: list[float] = []
    for j in range(population + 1):
        if j < k_seen or population - j < n_seen - k_seen:
            logs.append(-math.inf)
        else:
            logs.append(
                math.lgamma(j + 1) - math.lgamma(k_seen + 1) - math.lgamma(j - k_seen + 1)
                + math.lgamma(population - j + 1) - math.lgamma(n_seen - k_seen + 1)
                - math.lgamma(population - j - n_seen + k_seen + 1)
            )
    return _normalised(logs)


def central_interval(pmf: Sequence[float], confidence: float = DEFAULT_CONFIDENCE) -> tuple[int, int]:
    """The equal-tailed interval: the quantiles leaving (1 - confidence)/2 on each side.

    Equal-tailed, not shortest: a skewed pmf has a shorter interval elsewhere.
    """
    tail = (1.0 - confidence) / 2.0
    lower, upper = 0, len(pmf) - 1
    cumulative = 0.0
    for i, p in enumerate(pmf):
        cumulative += p
        if cumulative >= tail:
            lower = i
            break
    cumulative = 0.0
    for i in range(len(pmf) - 1, -1, -1):
        cumulative += pmf[i]
        if cumulative >= tail:
            upper = i
            break
    return lower, upper


def tail_at_least(pmf: Sequence[float], minimum: int) -> float:
    return float(sum(pmf[minimum:])) if minimum < len(pmf) else 0.0


def candidates_for_chance(k: int, n: int, minimum: int, chance: float) -> int | None:
    """The smallest fresh discovery whose chance of ``minimum`` reaches ``chance``.

    Galloping search then bisection on a monotone function; ``None`` when even
    ``SEARCH_CAP`` candidates do not reach it. The returned size never exceeds
    ``SEARCH_CAP``.
    """
    def reaches(t: int) -> bool:
        return tail_at_least(beta_binomial_pmf(t, k, n), minimum) >= chance

    if minimum > SEARCH_CAP:
        return None
    if reaches(minimum):
        return minimum
    lo, hi = minimum, min(minimum * 2, SEARCH_CAP)
    while not reaches(hi):
        if hi >= SEARCH_CAP:
            return None
        lo, hi = hi, min(hi * 2, SEARCH_CAP)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if reaches(mid):
            hi = mid
        else:
            lo = mid
    return hi
