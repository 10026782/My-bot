# gunicorn.conf.py — auto-loaded by gunicorn from the working directory
# when no -c/--config flag is given (Render's Start Command stays exactly
# `gunicorn app:app` — no change needed there).
#
# PATCH 3B Step 5 fix: importing app.py (to grab the WSGI `app` object)
# must not, by itself, reach Airtable or start the scheduler. Those two
# things now live in app.run_startup_sequence(), called from here —
# post_worker_init runs once per worker, after the worker process has
# fully initialized (module import already complete), which is gunicorn's
# documented hook for exactly this kind of "start background services
# after fork, not as an import side effect" startup work.

# PATCH 3B Step 5.1 (P0): pinned to a single worker.
#
# scheduler.py's scheduler thread — and, as of Step 5, the
# EmergencyStopManager bootstrap/hydration — are in-process state.
# post_worker_init runs once PER WORKER, but the "is a thread named
# 'scheduler' already alive?" dedup check in app.run_startup_sequence() is
# process-local: it has no visibility across worker processes. With more
# than one worker, each worker would independently start its own scheduler
# thread — N schedulers all firing the same jobs (digest, payment
# reminders, etc.) on the same timers, N-way duplicated. Multiple Render
# instances have the exact same problem, one level up (no shared lock
# across machines either).
#
# Do NOT raise this above 1, and do NOT scale to multiple Render instances,
# until there's a distributed scheduler or a leader-election lock that
# makes "exactly one active scheduler across all workers/instances" true
# regardless of worker/instance count. That's out of scope for PATCH 3B.
workers = 1

# PROD-INCIDENT 04/10/2026: two people (owner + partner) opening the TMA
# at the same time -- one of them stalls until the other's request(s)
# finish, with no error status anywhere (confirmed via Render log replay:
# every request eventually returns 200, nothing 5xx/times-out server-side,
# but a single page load retried itself 5x in 7s). Root cause: the "sync"
# worker class (gunicorn's default when unset) processes exactly one HTTP
# request at a time per worker, with no concurrency inside a worker at
# all -- combined with workers=1 above, that means the ENTIRE app (bot
# webhook + TMA API + health checks) serializes globally, one request at
# a time, process-wide. Airtable reads take long enough (TMA screens issue
# several sequential calls) that a second person's request simply queues
# behind the first's until it's done.
#
# Fix: "gthread" worker class with a small thread pool, workers left at 1.
# This does NOT add a second process -- post_worker_init above still runs
# exactly once, so the scheduler/EmergencyStopManager single-instance
# invariant above is untouched -- it only lets that one process hold
# several requests in flight at once via a thread pool, which is exactly
# what's needed for I/O-bound work (blocking httpx calls to Airtable/
# Telegram release the GIL while waiting on the network).
#
# Already-thread-safe-by-construction call sites that make this change
# low-risk: event_bus.PendingActionsStore (LL-13 lock around get+delete),
# guards.rate_limiter.RateLimiter (its own lock), tma_api._APPROVAL_LOCKS
# (per-approval-id lock dict guarded by _APPROVAL_LOCKS_GUARD). A full
# thread-safety audit of every remaining global was NOT performed -- if a
# new unguarded shared-mutable-state bug shows up under real concurrent
# load, that's the next thing to look at, not a reason to revert this.
worker_class = "gthread"
threads = 4


def post_worker_init(worker):
    import app as _app
    _app.run_startup_sequence()
