import json
import os
import sys
from pathlib import Path

os.environ["HOME"] = sys.argv[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_mfa import Backend, MemoryStore, fixture

store = MemoryStore()
store.value["accounts"] = [fixture("Alpha"), fixture("中文 Beta")]
store.value["accounts"][1].update(algorithm="SHA512", digits=7, period=60)
service = Backend(store)
for line in sys.stdin:
    request = json.loads(line)
    try:
        data = service.dispatch(request)
        reply = dict(id=request["id"], ok=True, data=data)
        with open(sys.argv[2], "a") as trace:
            trace.write(request["op"] + "\n")
        if request["op"] == "import":
            Path(sys.argv[3]).write_text(json.dumps(store.value))
    except Exception as error:
        reply = dict(id=request["id"], ok=False, error=str(error))
    print(json.dumps(reply), flush=True)
