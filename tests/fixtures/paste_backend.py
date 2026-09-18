"""Delayed RPC responses without a keyring or clipboard."""

import json
import os
import sys
import time

mode = os.environ["MFA_TEST_MODE"]
for line in sys.stdin:
    request = json.loads(line)
    with open(os.environ["MFA_TEST_TRACE"], "a") as trace:
        trace.write(request["op"] + "\n")
    reply = {"id": request["id"], "ok": True, "data": {}}
    if request["op"] == "list":
        reply["data"] = {
            "accounts": [
                {
                    "id": "fixture",
                    "name": "Fixture",
                    "code": "123456",
                    "period": 30,
                    "expiresAt": 9999999999,
                }
            ]
        }
    elif request["op"] == "copy":
        time.sleep(0.4)
        if mode == "malformed":
            print("invalid json", flush=True)
            continue
        if mode == "malformed_null":
            print("null", flush=True)
            continue
        if mode == "malformed_id":
            print(json.dumps({"id": -1, "ok": True, "data": {}}), flush=True)
            continue
        if mode == "copy_failed":
            reply = {"id": request["id"], "ok": False, "error": "keyring_write_failed"}
        elif request.get("paste"):
            reply["data"] = {"pasteToken": "fixture-handoff"}
    elif request["op"] == "paste":
        time.sleep(0.1)
        if mode == "paste_failed":
            reply = {"id": request["id"], "ok": False, "error": "paste_failed"}
    print(json.dumps(reply), flush=True)
