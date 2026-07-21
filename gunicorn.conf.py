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


def post_worker_init(worker):
    import app as _app
    _app.run_startup_sequence()
