import json
import sys
import time

for line in sys.stdin:
    request = json.loads(line)
    rows = [
        dict(
            id="fixture-" + str(i),
            name="Fixture " + str(i),
            code="123456",
            expiresAt=9999999999,
            period=30,
            algorithm="SHA1",
            digits=6,
            lastUsed=0,
        )
        for i in range(40)
    ]
    data = dict(accounts=rows)
    if request["op"] == "preview":
        data = dict(
            token="fixture-preview",
            rows=[
                dict(index=i, row=i + 1, name="Fixture backup " + str(i), error="", conflict=False)
                for i in range(3)
            ],
        )
    elif request["op"] == "cancel_preview":
        data = {}
    time.sleep(0.15)
    print(json.dumps(dict(id=request["id"], ok=True, data=data)), flush=True)
