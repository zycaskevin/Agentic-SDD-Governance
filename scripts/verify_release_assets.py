#!/usr/bin/env python3
"""Verify the complete public release inventory after artifact download."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

if __package__:
    from .release_files import SAFE_NAME, open_directory
else:  # pragma: no cover - exercised by direct release workflow execution
    from release_files import SAFE_NAME, open_directory


MANIFEST_ROW = re.compile(r"([a-f0-9]{64})  ([^\r\n]+)")
MAX_PUBLIC_MANIFEST_BYTES = 64 * 1024


def verify_release_assets(root: Path) -> dict[str, Any]:
    with open_directory(root, "downloaded release root") as release:
        with release.open_regular_file(
            "SHA256SUMS.txt", "public release manifest"
        ) as manifest:
            if manifest.initial_metadata.st_size > MAX_PUBLIC_MANIFEST_BYTES:
                raise ValueError("public release manifest exceeds the size limit")
            try:
                rows = manifest.read_text(encoding="ascii").splitlines()
            except UnicodeDecodeError as exc:
                raise ValueError("public release manifest must be ASCII") from exc

        if not rows:
            raise ValueError("public release manifest is empty")
        expected: dict[str, str] = {}
        for row in rows:
            match = MANIFEST_ROW.fullmatch(row)
            if match is None:
                raise ValueError("public release manifest has an invalid row")
            digest, name = match.groups()
            if SAFE_NAME.fullmatch(name) is None or name in {".", ".."}:
                raise ValueError("public release manifest has an unsafe asset name")
            if name in expected:
                raise ValueError("public release manifest has a duplicate asset")
            expected[name] = digest

        with release.open_directory(
            "distributions", "downloaded release distributions"
        ) as distributions:
            distribution_names = set(distributions.names())
            root_asset_names = set(release.names()) - {
                "SHA256SUMS.txt",
                "distributions",
                "offline",
            }
            if distribution_names & root_asset_names:
                raise ValueError(
                    "downloaded release assets have ambiguous duplicate names"
                )
            if set(expected) != distribution_names | root_asset_names:
                raise ValueError(
                    "public release manifest does not exactly cover downloaded assets"
                )
            for name, digest in expected.items():
                owner = distributions if name in distribution_names else release
                with owner.open_regular_file(
                    name, "downloaded public release asset"
                ) as asset:
                    if asset.sha256() != digest:
                        raise ValueError("downloaded public release asset digest mismatch")

        return {
            "ok": True,
            "asset_count": len(expected),
            "assets": sorted(expected),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        report = verify_release_assets(args.root)
    except (OSError, ValueError):
        print("release asset verification failed")
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
