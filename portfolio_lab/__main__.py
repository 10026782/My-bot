"""python3 -m portfolio_lab < scenario.json — strict JSON in/out."""

import json
import sys

from . import Scenario, compare, simulate


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    try:
        data = json.load(sys.stdin, object_pairs_hook=_unique_object)
        if isinstance(data, dict) and "strategies" in data:
            if set(data) != {"strategies"} or not isinstance(data["strategies"], dict):
                raise ValueError("comparison must contain only a strategies object")
            result = compare({name: Scenario.from_dict(s) for name, s in data["strategies"].items()})
        else:
            result = simulate(Scenario.from_dict(data))
        output = json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
