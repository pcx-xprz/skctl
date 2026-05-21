"""Test berbagai format request ke Sky API."""
import requests
import msgpack

SESSION = "cd96b914-221b-4ad4-9635-d93f107dc4a4"
USER_ID = "6d1edd3e-9a1f-4f39-8b70-aa198babb753"
UA      = "Sky-Live-com.tgc.sky.android/0.33.2.384474 (Xiaomi M2101K7BNY; android 33.0.0; id)"
URL     = "https://live.radiance.thatgamecompany.com/account/get_currency"

base_headers = {
    "User-Agent":  UA,
    "session":     SESSION,
    "user-id":     USER_ID,
    "Accept":      "application/x-msgpack, */*",
}

tests = [
    # (nama, body, extra_headers)
    ("1. msgpack {user+session}",
     msgpack.packb({"user": USER_ID, "session": SESSION}, use_bin_type=True),
     {"Content-Type": "application/x-msgpack"}),

    ("2. msgpack {} kosong",
     msgpack.packb({}, use_bin_type=True),
     {"Content-Type": "application/x-msgpack"}),

    ("3. msgpack {user+session} integer keys",
     msgpack.packb({1: USER_ID, 2: SESSION}, use_bin_type=True),
     {"Content-Type": "application/x-msgpack"}),

    ("4. JSON {user+session}",
     b'{"user":"' + USER_ID.encode() + b'","session":"' + SESSION.encode() + b'"}',
     {"Content-Type": "application/json; charset=utf-8"}),

    ("5. body kosong total",
     b"",
     {"Content-Type": "application/x-msgpack"}),
]

for name, body, extra_h in tests:
    h = {**base_headers, **extra_h}
    try:
        r = requests.post(URL, data=body, headers=h, timeout=10)
        print(f"{name}: HTTP {r.status_code} | body={len(body)}B | resp={len(r.content)}B | CT={r.headers.get('Content-Type','?')}")
        if r.content:
            try:
                print(f"  response: {msgpack.unpackb(r.content, raw=False)}")
            except Exception:
                print(f"  response raw: {r.content[:100]}")
    except Exception as e:
        print(f"{name}: ERROR {e}")
