#!/usr/bin/env python3
"""PROVENANCE: written-by codex/gpt-6.1-sol, 2026-11-10; commit recorded by Git history. Verify package bytes; execute no package code."""
from pathlib import Path
import hashlib
root = Path(__file__).resolve().parent
count = 0
for line in (root / "SHA256SUMS").read_text().splitlines():
    expected, name = line.split("  ", 1)
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise SystemExit("Unsafe checksum path")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("Checksum mismatch: " + name)
    count += 1
print(f"Verified {count} package files")
