"""Run isolated registry tests and compile the installed RE2 literal matcher."""
from pathlib import Path
import shlex
import subprocess
root=Path(__file__).resolve().parent.parent
subprocess.run(['lua','tests/behavior.lua'],cwd=root,check=True)
subprocess.run(['luac','-p','configuration-example.lua'],cwd=root,check=True)
build=root/'tests/build';build.mkdir(exist_ok=True)
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','re2'],text=True))
subprocess.run(['c++','-std=c++17','-o',str(build/'re2-literals'),'tests/re2-literals.cpp',*flags],cwd=root,check=True)
data=subprocess.check_output(['lua','tests/re2-input.lua'],cwd=root)
subprocess.run([str(build/'re2-literals')],input=data,cwd=root,check=True)
