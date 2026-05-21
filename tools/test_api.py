"""Test berbagai format request ke Sky API."""
import requests
import sys

SESSION = sys.argv[1] if len(sys.argv) > 1 else "GANTI_DENGAN_SESSION_BARU"
USER_ID = sys.argv[2] if len(sys.argv) > 2 else "6d1edd3e-9a1f-4f39-8b70-aa198babb753"
UA      = "Sky-Live-com.tgc.sky.android/0.33.2.384474 (Xiaomi M2101K7BNY; android 33.0.0; id)"
URL     = "https://live.radiance.thatgamecompany.com/account/get_currency"

print(f"Testing session: {SESSION[:16]}...")
print(f"user_id: {USER_ID}\n")

base_headers = {
    "User-Agent": UA,
    "session":    SESSION,
    "user-id":    USER_ID,
}

import json

tests = [
    ("1. JSON {user+session}",
     json.dumps({"user": USER_ID, "session": SESSION}).encode(),
     {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}),

    ("2. JSON {} kosong",
     b"{}",
     {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}),

    ("3. body kosong",
     b"",
     {"Content-Type": "application/json; charset=utf-8"}),
]

try:
    import msgpack
    tests += [
        ("4. msgpack {user+session}",
         msgpack.packb({"user": USER_ID, "session": SESSION}, use_bin_type=True),
         {"Content-Type": "application/x-msgpack", "Accept": "application/x-msgpack"}),
        ("5. msgpack {} kosong",
         msgpack.packb({}, use_bin_type=True),
         {"Content-Type": "application/x-msgpack", "Accept": "application/x-msgpack"}),
    ]
except ImportError:
    print("msgpack tidak terinstall, skip test 4&5\n")

for name, body, extra_h in tests:
    h = {**base_headers, **extra_h}
    try:
        r = requests.post(URL, data=body, headers=h, timeout=10)
        print(f"{name}: HTTP {r.status_code} | body={len(body)}B | resp={len(r.content)}B")
        if r.content:
            try:
                print(f"  >> {r.json()}")
            except Exception:
                print(f"  >> raw: {r.content[:200]}")
        print()
    except Exception as e:
        print(f"{name}: ERROR {e}\n")
