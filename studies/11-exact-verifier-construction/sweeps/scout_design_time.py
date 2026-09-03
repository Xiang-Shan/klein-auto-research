"""Design-time scouting for study 11. Disclosed in scouting_ledger.md."""
from itertools import combinations
from math import gcd
import random, time


def collinear(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0


# S1 --- Erdos parabola construction {(x, x^2 mod p)} at several primes
for p in (7, 11, 13, 31):
    pts = [(x, (x * x) % p) for x in range(p)]
    bad = [t for t in combinations(pts, 3) if collinear(*t)]
    print(f"S1 p={p}: {len(pts)} points, distinct={len(set(pts))}, collinear triples={len(bad)}")

# S2 --- cost of one addability test (timing only; no search is run)
def norm_table(n):
    tab = {}
    for dx in range(-(n - 1), n):
        for dy in range(-(n - 1), n):
            if dx == 0 and dy == 0:
                continue
            g = gcd(abs(dx), abs(dy))
            u, v = dx // g, dy // g
            if u < 0 or (u == 0 and v < 0):
                u, v = -u, -v
            tab[(dx, dy)] = (u, v)
    return tab


def bench(n, k, trials=20000):
    tab = norm_table(n)
    rng = random.Random(0)
    cells = [(x, y) for x in range(n) for y in range(n)]
    S = rng.sample(cells, k)
    probe = [rng.choice(cells) for _ in range(trials)]
    t0 = time.perf_counter()
    for p in probe:
        seen = set()
        for q in S:
            d = tab.get((q[0] - p[0], q[1] - p[1]))
            if d is None:
                continue
            if d in seen:
                break
            seen.add(d)
    dt = time.perf_counter() - t0
    print(
        f"S2 n={n} |S|={k}: {dt / trials * 1e6:.2f} us per addability test "
        f"-> 200000 tests = {dt / trials * 200000:.2f} s"
    )


bench(11, 22)
bench(31, 62)
