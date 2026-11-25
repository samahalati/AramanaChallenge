"""Small load test (standard library only): mixed read workload + audited writes, then verifies the audit hash chain.

    python backend/scripts/loadtest.py --base http://localhost:8080 --seconds 30 --threads 16

Reads: alert list/detail, monitoring overview, HR practitioners, supervision dashboard.  Writes: alert comments (each one appends to the audit chain,
so concurrent replicas are exercised).  Prints throughput, latency percentiles and error counts per endpoint; exit code 1 on any error or a broken chain.
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

PASSWORD = "Demo!2345"


def call(base, method, path, token=None, body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:   # connection refused / reset / timeout
        return 0, None


def login(base, email):
    status, data = call(base, "POST", "/api/auth/login", body={"email": email, "password": PASSWORD})
    assert status == 200, f"login failed for {email}: {status}"
    return data["access_token"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()

    comp, hr, sup = (login(a.base, f"{n}@aramana.test") for n in ("compliance", "hr", "supervisor1"))
    alert_ids = [x["id"] for x in call(a.base, "GET", "/api/alerts?limit=50", comp)[1]["items"]]
    workload = [  # (name, method, path, token, body)
        ("alerts list", "GET", "/api/alerts?limit=20", comp, None),
        ("alert detail", "GET", "/api/alerts/{id}", comp, None),
        ("overview", "GET", "/api/monitoring/summary", comp, None),
        ("practitioners", "GET", "/api/hr/practitioners", hr, None),
        ("supervision dashboard", "GET", "/api/supervision/dashboard", sup, None),
        ("alert comment (audited write)", "POST", "/api/alerts/{id}/actions", comp, {"action": "comment", "note": "load test note"}),
    ]
    results, lock, stop = {w[0]: [] for w in workload}, threading.Lock(), time.time() + a.seconds

    def worker(seed):
        i = seed
        while time.time() < stop:
            name, method, path, token, body = workload[i % len(workload)]
            path = path.replace("{id}", str(alert_ids[i % len(alert_ids)]))
            t0 = time.perf_counter()
            status, _ = call(a.base, method, path, token, body)
            with lock:
                results[name].append((time.perf_counter() - t0, status))
            i += 1

    started = time.time()
    threads = [threading.Thread(target=worker, args=(n,)) for n in range(a.threads)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    elapsed = time.time() - started

    total = errors = 0
    print(f"{'endpoint':34} {'n':>6} {'err':>5} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8}")
    for name, rows in results.items():
        lat = sorted(r[0] * 1000 for r in rows)
        err = sum(1 for r in rows if r[1] != 200)
        total, errors = total + len(rows), errors + err
        if lat:
            q = statistics.quantiles(lat, n=100, method="inclusive") if len(lat) > 1 else [lat[0]] * 99
            print(f"{name:34} {len(lat):6} {err:5} {q[49]:8.0f} {q[94]:8.0f} {q[98]:8.0f}")
    print(f"\n{total} requests in {elapsed:.0f}s = {total / elapsed:.0f} req/s with {a.threads} threads; errors: {errors}")
    chain = call(a.base, "GET", "/api/audit/verify", comp)[1]
    print("audit hash chain:", chain)
    sys.exit(0 if errors == 0 and chain and chain.get("ok") else 1)


if __name__ == "__main__":
    main()
