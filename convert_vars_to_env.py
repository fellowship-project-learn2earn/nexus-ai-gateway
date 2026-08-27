#!/usr/bin/env python3
"""
Converts an exported n8n Cloud workflow JSON from $vars.X (Enterprise-only
on self-hosted) to $env.X (works on self-hosted Community Edition by
default). Run this on your downloaded workflow export before importing
it into the Dockerized instance.

Usage:
    python3 convert_vars_to_env.py your-exported-workflow.json
"""

import json
import sys


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 convert_vars_to_env.py <workflow.json>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        content = f.read()

    before_count = content.count("$vars.")
    converted = content.replace("$vars.", "$env.")
    after_count = converted.count("$env.")

    # validate it's still valid JSON after the text replace
    json.loads(converted)

    output_path = path.replace(".json", "-self-hosted.json")
    with open(output_path, "w") as f:
        f.write(converted)

    print(f"Converted {before_count} $vars. references to $env.")
    print(f"Total $env. references now in file: {after_count}")
    print(f"Written to: {output_path}")
    print()
    print("Import THIS file into your Dockerized n8n instance, not the original.")


if __name__ == "__main__":
    main()
