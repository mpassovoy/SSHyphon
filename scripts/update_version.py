#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_ROOT / "VERSION"
VERSION_JSON_FILE = PROJECT_ROOT / "VERSION.json"


TAG_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")


def detect_git_tag() -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("No git tag found for the current commit")
    return result.stdout.strip()


def parse_tag(tag: str) -> str:
    match = TAG_PATTERN.match(tag)
    if not match:
        raise ValueError("Tag must match vX.Y.Z")
    return match.group(1)


def write_version_files(version: str, include_metadata: bool = True) -> None:
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")
    if include_metadata:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        VERSION_JSON_FILE.write_text(
            json.dumps(
                {
                    "version": version,
                    "commit": sha,
                    "built_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the VERSION file from a release tag")
    parser.add_argument("tag", nargs="?", help="Release tag in the form vX.Y.Z. Defaults to the current git tag")
    parser.add_argument("--skip-json", action="store_true", help="Do not write VERSION.json")
    args = parser.parse_args()

    tag = args.tag or detect_git_tag()
    version = parse_tag(tag)

    write_version_files(version, include_metadata=not args.skip_json)
    print(f"Wrote version {version} from tag {tag}")


if __name__ == "__main__":
    main()
