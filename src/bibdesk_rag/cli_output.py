"""Readable results with all returned provenance; JSON remains explicit."""

from __future__ import annotations

import json


def text_value(value: object) -> str:
    if isinstance(value, str):
        return "".join(c if c.isprintable() else json.dumps(c)[1:-1] for c in value)
    return json.dumps(value, ensure_ascii=False)


def print_result(value: object, output_format: str, indent: int = 0) -> None:
    if output_format == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, dict):
        for key, item in value.items():
            prefix = " " * indent + text_value(key) + ":"
            if isinstance(item, (dict, list)) and item:
                print(prefix)
                print_result(item, "text", indent + 2)
            else:
                print(prefix + " " + text_value(item))
    elif isinstance(value, list):
        if not value:
            print(" " * indent + "No results.")
        for number, item in enumerate(value, 1):
            print(" " * indent + f"[{number}]")
            print_result(item, "text", indent + 2)
    else:
        print(" " * indent + text_value(value))
