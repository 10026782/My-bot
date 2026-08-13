# Isolated SCOREBOS research crawler POC

This directory is not imported by the SCOREBOS runtime. Run it only in a disposable virtual environment. It accepts only the approved hosts declared in `crawl.py`, uses no credentials/cookies, and writes to `/tmp` by default.

```bash
python3 -m venv /tmp/scorebos-crawler-venv
/tmp/scorebos-crawler-venv/bin/pip install -r requirements.txt
/tmp/scorebos-crawler-venv/bin/python crawl.py --url https://nosignups.net/
```

Do not pass arbitrary URLs, production data, authenticated pages, private hosts or secrets. The script is a measurement harness, not a service and not a registry writer.
