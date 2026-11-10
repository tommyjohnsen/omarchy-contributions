"""Run the native probe with render-only devices and no display/seat control nodes.
SPDX-License-Identifier: MIT
"""
import argparse
from pathlib import Path
import os
import stat
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--premap-client', type=Path, required=True)
parser.add_argument('--render-node', type=Path, required=True)
parser.add_argument('--tag', default='render-only-v4')
args = parser.parse_args()
root = Path(__file__).resolve().parent
node = args.render_node.resolve(strict=True)
info = node.stat()
assert node.name.startswith('renderD') and node.name[7:].isdigit()
assert stat.S_ISCHR(info.st_mode) and os.major(info.st_rdev) == 226 and os.minor(info.st_rdev) >= 128
subprocess.run([
    'bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--dir', '/dev/dri',
    '--dev-bind', str(node), '/dev/dri/' + node.name, '--tmpfs', '/run/dbus',
    '--bind', '/tmp', '/tmp', '--bind', str(root), str(root),
    '/usr/bin/python', str(root / 'nested-minimize-test.py'), '--tag', args.tag,
    '--expect-premap', '0', '--binary', str(args.binary.resolve(strict=True)),
    '--premap-client', str(args.premap_client.resolve(strict=True)),
], check=True)
