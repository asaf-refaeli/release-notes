"""Call the app in a loop during a rollout and count failed requests (target: zero).

Usage: uv run scripts/rollout_check.py http://prod.localhost 300
"""

import sys
import time
from collections import Counter
from urllib.parse import urlsplit

import httpx2

url = sys.argv[1]
duration = int(sys.argv[2])

# *.localhost means this machine (RFC 6761). Browsers and curl know that, but Python
# asks the OS, which may not. So connect to 127.0.0.1 and send the name in the Host
# header, which is what Traefik routes by.
headers = {}
host = urlsplit(url).hostname
if host.endswith(".localhost"):
    headers["Host"] = host
    url = url.replace(host, "127.0.0.1", 1)

results = Counter()  # "ok", or what failed: "502", "ConnectError", ...
versions = {}  # version -> [first second seen, last second seen]
start = time.monotonic()

print(f"Sending requests to {sys.argv[1]} for {duration} s, please wait...")

with httpx2.Client(base_url=url, headers=headers, timeout=5.0) as client:
    while time.monotonic() - start < duration:
        second = int(time.monotonic() - start)
        try:
            client.get("/api/releases").raise_for_status()
            response = client.get("/api/version")
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            results[str(exc.response.status_code)] += 1
        except httpx2.TransportError as exc:
            results[type(exc).__name__] += 1
        else:
            results["ok"] += 1
            version = response.json()["version"]
            if version not in versions:
                versions[version] = [second, second]
            versions[version][1] = second

failed = results.total() - results["ok"]
print(f"ok: {results['ok']}  failed: {failed}  details: {dict(results)}")
for version, (first, last) in versions.items():
    print(f"{version}: seen from {first}s to {last}s")
sys.exit(1 if failed else 0)
