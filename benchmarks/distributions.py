"""Seeded length distributions for workload generation.

Specs: "fixed:N", "uniform:LO:HI", "lognormal:MEDIAN:SIGMA:LO:HI" (log-normal clipped
to [LO, HI]). Defaults used by the realistic-traffic experiments are ISL lognormal with a
4K median clipped to 2K-16K, and OSL lognormal with a 512 median clipped to 256-2K.
"""
import math
import random

DEFAULT_ISL = 'lognormal:4000:0.6:2000:16000'
DEFAULT_OSL = 'lognormal:512:0.6:256:2048'


def parse(spec):
    kind, *args = spec.split(':')
    nums = [float(a) for a in args]
    if kind == 'fixed' and len(nums) == 1 and nums[0] >= 1:
        return kind, nums
    if kind == 'uniform' and len(nums) == 2 and 1 <= nums[0] <= nums[1]:
        return kind, nums
    if kind == 'lognormal' and len(nums) == 4 and nums[0] > 0 and nums[1] >= 0 and 1 <= nums[2] <= nums[3]:
        return kind, nums
    raise ValueError(f'invalid distribution spec {spec!r}; use fixed:N, uniform:LO:HI or lognormal:MEDIAN:SIGMA:LO:HI')


def sample(spec, rng):
    kind, n = parse(spec)
    if kind == 'fixed':
        return int(n[0])
    if kind == 'uniform':
        return rng.randint(int(n[0]), int(n[1]))
    median, sigma, lo, hi = n
    return int(min(hi, max(lo, round(math.exp(rng.gauss(math.log(median), sigma))))))


def sampler(spec, seed, stream):
    """Independent, reproducible stream per (seed, purpose); never shares state with other RNGs."""
    rng = random.Random(f'{seed}:{stream}')
    return lambda: sample(spec, rng)
