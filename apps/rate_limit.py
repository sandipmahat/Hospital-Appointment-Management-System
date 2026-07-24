"""
Minimal in-memory rate limiter for login attempts.

This is intentionally simple: it tracks failed attempts per (email, IP) pair
in a process-local, thread-safe dict with a sliding time window. That's
enough to blunt naive credential-stuffing / brute-force attempts against a
single account in a single-process deployment (matching how this app is
run). It is NOT a substitute for a shared store like Redis in a
multi-process/multi-instance production deployment, where each worker would
otherwise track attempts independently.
"""
import time
from collections import defaultdict, deque
from threading import Lock

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60  # 1 minute

_attempts = defaultdict(deque)
_lock = Lock()


def _prune(key, now):
    attempts = _attempts[key]
    while attempts and now - attempts[0] > WINDOW_SECONDS:
        attempts.popleft()


def is_rate_limited(key):
    now = time.time()
    with _lock:
        _prune(key, now)
        return len(_attempts[key]) >= MAX_ATTEMPTS


def record_failed_attempt(key):
    now = time.time()
    with _lock:
        _prune(key, now)
        _attempts[key].append(now)


def reset_attempts(key):
    with _lock:
        _attempts.pop(key, None)


def seconds_until_retry(key):
    with _lock:
        attempts = _attempts.get(key)
        if not attempts:
            return 0
        oldest = attempts[0]
        remaining = WINDOW_SECONDS - (time.time() - oldest)
        return max(0, int(remaining))
