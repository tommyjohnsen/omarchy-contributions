#!/usr/bin/env bash
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
mkdir "$scratch/candidate"
ln -s "$repo_root/altswitch.lua" "$scratch/candidate/altswitch.lua"
ln -s "$repo_root/AltSwitch.qml" "$scratch/candidate/AltSwitch.qml"
cd "$scratch"
lua "$repo_root/tests/behavior.lua"
python3 "$repo_root/tests/plaintext-and-quoting.py"
