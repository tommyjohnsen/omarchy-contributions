"""Run in render-only bwrap: assert KMS/card and input device nodes are absent."""
from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parent
dri=Path("/dev/dri")
proof={"card_nodes":[p.name for p in dri.glob("card*")],"render_nodes":[p.name for p in dri.glob("renderD*")],"dev_input_present":Path("/dev/input").exists(),"system_bus_present":Path("/run/dbus/system_bus_socket").exists(),"seatd_socket_present":Path("/run/seatd.sock").exists()}
assert not proof["card_nodes"] and not proof["dev_input_present"] and proof["render_nodes"] and not proof["system_bus_present"] and not proof["seatd_socket_present"],proof
(root/"device-isolation.json").write_text(json.dumps(proof,indent=2)+"\n")
os.execv("/usr/bin/python3",["/usr/bin/python3","-B",str(root/"verify.py"),*sys.argv[1:]])
