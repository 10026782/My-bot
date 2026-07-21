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


def post_worker_init(worker):
    import app as _app
    _app.run_startup_sequence()
