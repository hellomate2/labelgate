import math
import random


def wilson(k, n, z=1.959964):
    """Wilson score interval for k successes out of n. Returns (low, high), or (None, None) when n is 0."""
    if n == 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def paired_bootstrap(a, b, resamples=10000, seed=0):
    """Mean of a minus mean of b over the same rows, with a 95% percentile interval.

    a and b are equal-length lists of 0/1 outcomes on the same rows.
    """
    if len(a) != len(b) or not a:
        raise ValueError("need two equal, non-empty lists")
    rng = random.Random(seed)
    n = len(a)
    diffs = [x - y for x, y in zip(a, b)]
    means = []
    for _ in range(resamples):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return sum(diffs) / n, means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]
