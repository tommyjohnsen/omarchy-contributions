#!/usr/bin/env bash
set -euo pipefail
artifact_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
render_node=${OMARCHY_TEST_RENDER_NODE:-/dev/dri/renderD128}
[[ $render_node =~ ^/dev/dri/renderD[0-9]+$ ]] || { echo 'Expected one renderD device path' >&2; exit 2; }
exec /usr/bin/bwrap --die-with-parent --ro-bind / / --dev /dev --tmpfs /run/dbus --dir /dev/dri --dev-bind "$render_node" "$render_node" --bind /tmp /tmp --bind "$artifact_dir" "$artifact_dir" /usr/bin/python3 -B "$artifact_dir/sandbox_bootstrap.py" "$@"
