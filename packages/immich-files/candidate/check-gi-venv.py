#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Disposable system-site-packages GI import check; never accesses a keyring."""
from pathlib import Path
import json,platform,subprocess,tempfile
with tempfile.TemporaryDirectory(prefix='immich-gi-venv-') as directory:
 subprocess.run(['/usr/bin/python','-m','venv','--system-site-packages',directory],check=True,capture_output=True,timeout=30)
 result=subprocess.run([str(Path(directory)/'bin/python'),'-c','import gi;gi.require_version("Secret","1");from gi.repository import Secret;print("GI Secret typelib import passed")'],capture_output=True,text=True,timeout=10)
 assert result.returncode==0,'Fresh system-site-packages venv could not import GI/Secret'
 print(json.dumps({'system_python_version':platform.python_version(),'fresh_system_site_packages_venv':True,'gi_secret_typelib_import':True,'keyring_access_performed':False}))
