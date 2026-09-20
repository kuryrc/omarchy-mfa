"""Public, fixed display data for documentation; no storage or desktop integrations."""

import json
import sys

NOW = 1700000000
EXAMPLES = [
    ("GitHub · demo@example.com", "123456", 24, 30, "SHA1"),
    ("GitLab · dev@example.com", "234567", 24, 30, "SHA1"),
    ("Cloudflare · team@example.com", "345678", 24, 30, "SHA256"),
    ("Proton · demo@example.com", "456789", 24, 30, "SHA1"),
    ("Example VPN · work@example.com", "01234567", 54, 60, "SHA512"),
]

for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "list":
        data = {
            "accounts": [
                {
                    "id": f"demo-{index}",
                    "name": name,
                    "code": code,
                    "expiresAt": NOW + remaining,
                    "period": period,
                    "algorithm": algorithm,
                    "digits": len(code),
                    "lastUsed": 0,
                }
                for index, (name, code, remaining, period, algorithm) in enumerate(EXAMPLES)
            ],
            "settings": {"language": "en", "defaultAction": "copy"},
            "revision": "documentation-only",
        }
    elif request["op"] == "preview":
        data = {
            "token": "documentation-only",
            "rows": [
                {"index": 0, "row": 1, "name": "Example Cloud", "error": "", "conflict": False},
                {"index": 1, "row": 2, "name": EXAMPLES[0][0], "error": "", "conflict": True},
                {"index": 2, "row": 3, "name": "Example Mail", "error": "", "conflict": False},
                {
                    "index": 3,
                    "row": 4,
                    "name": "Invalid demo entry",
                    "error": "invalid_secret",
                    "conflict": False,
                },
            ],
        }
    else:
        raise SystemExit("Preview backend rejects all operations except list and preview")
    print(json.dumps({"id": request["id"], "ok": True, "data": data}), flush=True)
