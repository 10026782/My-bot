# Local hook installation

The local hook is an advisory reminder, not an authority gate:

```bash
git config core.hooksPath .githooks
```

After a local merge it may run:

```bash
python3 -m tools.context_librarian refresh-after-merge --check
```

Do not use a hook to write provenance from a feature branch. CI on `main` is the
authoritative post-merge behavior.
