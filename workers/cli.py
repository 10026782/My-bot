"""Manual, read-only/dry-run entry point for the Free Worker Pilot."""

from __future__ import annotations

import argparse
import json

from .contracts import WorkerRequest
from .registry import WorkerRegistry, WorkerRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "availability", "dry-run"))
    parser.add_argument("--role", default="builder")
    parser.add_argument("--task", default="inspect the repository")
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--allowed-path", action="append", default=["."])
    args = parser.parse_args(argv)
    registry = WorkerRegistry()
    if args.command == "list":
        print(json.dumps([p.to_dict() for p in registry.profiles.values()], default=str))
    elif args.command == "availability":
        print(json.dumps([a.__dict__ for a in registry.availability()]))
    else:
        request = WorkerRequest("dry-run", args.task, args.role, args.repo_path, allowed_paths=tuple(args.allowed_path))
        print(json.dumps(WorkerRouter(registry).dry_run(request).to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
