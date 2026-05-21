"""
fb_oauth_auto.py — Automated Facebook OAuth flow untuk Sky CoTL
================================================================
Cara pakai:
  1. Export cookies Facebook dari browser (pakai ekstensi "EditThisCookie" / "Cookie-Editor")
  2. Simpan sebagai JSON
  3. Jalankan: python fb_oauth_auto.py --cookies cookies.json

Atau langsung input cookie string:
  python fb_oauth_auto.py --cookie-string "c_user=...; xs=...; fr=..."
"""

import argparse
import json
import re
import sys
import time
from typing import Optional
import requests
from urllib.parse import urlencode, quote, urlparse, parse_qs

SKY_APP_ID      = "293746044767069"
REDIRECT_URI    = "https://live.radiance.thatgamecompany.com/account/auth/oauth_redirect"
STATE           = f"Facebook~{REDIRECT_URI}"
FB_BASE         = "https://web.facebook.com"
SKY_BASE        = "https://live.radiance.thatgamecompany.com"


class FacebookOAuthFlow:
    """Otomasi full Facebook OAuth → Sky token tanpa buka browser."""

    def __init__(self, cookies: dict, verbose: bool = False):
        self.s       = requests.Session()
        self.verbose = verbose
        self.s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        # Set cookies ke session
        for k, v in cookies.items():
            self.s.cookies.set(k, v, domain=".facebook.com")

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [DEBUG] {msg}")

    def step1_get_fb_dtsg(self) -> Optional[str]:
        """Step 1: Ambil fb_dtsg token dari halaman Facebook."""
        print("⏳ Step 1: Ambil fb_dtsg dari Facebook...")
        try:
            r = self.s.get(f"{FB_BASE}/", timeout=15)
            # Cari fb_dtsg di HTML
            patterns = [
                r'"DTSGInitialData".*?"token":"([^"]+)"',
                r'fb_dtsg.*?value="([^"]+)"',
                r'"fb_dtsg":"([^"]+)"',
                r'name="fb_dtsg" value="([^"]+)"',
                r'"jsSdkLibrary".*?"dtsg":"([^"]+)"',
            ]
            for pattern in patterns:
                match = re.search(pattern, r.text)
                if match:
                    dtsg = match.group(1)
                    print(f"  ✅ fb_dtsg: {dtsg[:20]}...")
                    return dtsg
            print("  ⚠️  fb_dtsg tidak ditemukan — cookie mungkin expired")
            self._log(f"HTML snippet: {r.text[:500]}")
            return None
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def step2_get_oauth_dialog(self, fb_dtsg: str) -> Optional[str]:
        """Step 2: POST ke games_service/save untuk dapat redirect URL dengan code."""
        print("⏳ Step 2: Request OAuth dialog ke Facebook...")

        import uuid
        logger_id = str(uuid.uuid4())

        url = (
            f"{FB_BASE}/v24.0/dialog/oauth/games_service/save/?"
            f"app_id={SKY_APP_ID}&"
            f"redirect_uri={quote(REDIRECT_URI)}&"
            f"state={quote(STATE)}&"
            f"response_type=code&"
            f"return_format[0]=code&"
            f"return_scopes=false&"
            f"scope[0]=openid&"
            f"scope[1]=gaming_profile&"
            f"display=page&"
            f"seen_scopes[0]=openid&"
            f"seen_scopes[1]=gaming_profile&"
            f"logger_id={logger_id}&"
            f"is_new_user_flow=false&"
            f"app_vis=3&"
            f"profile_type=gaming&"
            f"tp=unspecified&"
            f"is_limited_login_shim=false"
        )

        payload = {"fb_dtsg": fb_dtsg}
        headers = {
            "Content-Type":  "application/x-www-form-urlencoded",
            "Origin":        FB_BASE,
            "Referer":       f"{FB_BASE}/v24.0/dialog/oauth",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

        try:
            r = self.s.post(url, data=payload, headers=headers,
                            timeout=15, allow_redirects=False)
            self._log(f"POST status: {r.status_code}")
            self._log(f"Response headers: {dict(r.headers)}")
            self._log(f"Body[:500]: {r.text[:500]}")

            # Cari redirect URL di Location header
            loc = r.headers.get("Location", "")
            if loc and REDIRECT_URI.split("//")[1].split("/")[0] in loc:
                print(f"  ✅ Redirect ke Sky dengan code!")
                return loc

            # Atau di HTML (meta refresh)
            meta = re.search(r'content="0; URL=([^"]+)"', r.text)
            if meta:
                redirect_url = meta.group(1).replace("&amp;", "&")
                if REDIRECT_URI.split("//")[1].split("/")[0] in redirect_url:
                    print(f"  ✅ Redirect URL ditemukan di HTML!")
                    return redirect_url

            # Cari code langsung di response
            code_match = re.search(r'code=([A-Za-z0-9_\-]+)', r.text)
            if code_match:
                code = code_match.group(1)
                redirect_url = f"{REDIRECT_URI}?code={code}&state={quote(STATE)}"
                print(f"  ✅ Code ditemukan: {code[:20]}...")
                return redirect_url

            print(f"  ⚠️  Tidak dapat redirect URL (status={r.status_code})")
            print(f"  Body: {r.text[:300]}")
            return None

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def step3_exchange_code(self, redirect_url: str) -> Optional[dict]:
        """Step 3: Call Sky oauth_redirect dengan FB code."""
        print("⏳ Step 3: Exchange code ke Sky server...")
        try:
            r = requests.get(
                redirect_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/148.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://web.facebook.com/",
                },
                timeout=15,
                allow_redirects=True
            )
            self._log(f"Sky response: {r.status_code} | {r.text[:200]}")

            if r.status_code == 200:
                data = r.json()
                if data.get("token") and data.get("id"):
                    print(f"  ✅ Dapat token Sky!")
                    print(f"     id    : {data['id']}")
                    print(f"     alias : {data.get('alias','?')}")
                    print(f"     token : {str(data['token'])[:40]}...")
                    return data
                elif data.get("error"):
                    print(f"  ❌ Error dari Sky: {data['error']}")
            else:
                print(f"  ❌ Sky response: {r.status_code} | {r.text[:100]}")
            return None
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def run(self) -> Optional[dict]:
        """Jalankan full flow."""
        print("\n🚀 Mulai Facebook OAuth → Sky Token flow...\n")

        # Step 1
        fb_dtsg = self.step1_get_fb_dtsg()
        if not fb_dtsg:
            print("\n❌ GAGAL: Tidak bisa ambil fb_dtsg.")
            print("   Kemungkinan cookies expired. Export ulang dari browser.\n")
            return None

        # Step 2
        redirect_url = self.step2_get_oauth_dialog(fb_dtsg)
        if not redirect_url:
            print("\n❌ GAGAL: Tidak dapat redirect URL dari Facebook.")
            print("   Kemungkinan app Sky belum di-authorize di akun Facebook ini.\n")
            return None

        # Step 3
        sky_data = self.step3_exchange_code(redirect_url)
        if not sky_data:
            print("\n❌ GAGAL: Tidak dapat data dari Sky server.")
            return None

        print(f"\n✅ BERHASIL! JSON untuk bot:\n")
        result = {
            "id":    sky_data.get("id", ""),
            "alias": sky_data.get("alias", ""),
            "token": sky_data.get("token", ""),
        }
        print(json.dumps(result, indent=2))
        return result


def load_cookies_from_file(path: str) -> dict:
    """Load cookies dari file JSON (format EditThisCookie/Cookie-Editor)."""
    with open(path) as f:
        raw = json.load(f)

    cookies = {}
    if isinstance(raw, list):
        # Format: [{"name": "c_user", "value": "...", "domain": ".facebook.com"}, ...]
        for item in raw:
            name  = item.get("name") or item.get("key", "")
            value = item.get("value", "")
            if name and value:
                cookies[name] = value
    elif isinstance(raw, dict):
        # Format: {"c_user": "...", "xs": "..."}
        cookies = raw

    return cookies


def parse_cookie_string(cookie_str: str) -> dict:
    """Parse cookie string: 'c_user=xxx; xs=yyy; ...'"""
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    return cookies


def main():
    parser = argparse.ArgumentParser(
        description="Automated Facebook OAuth → Sky Token"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cookies",       metavar="FILE",   help="Path ke file cookies JSON")
    group.add_argument("--cookie-string", metavar="STRING", help="Cookie string dari browser")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug output")
    parser.add_argument("--output",  "-o", metavar="FILE",  help="Simpan hasil ke file JSON")
    args = parser.parse_args()

    # Load cookies
    if args.cookies:
        print(f"📂 Loading cookies dari: {args.cookies}")
        cookies = load_cookies_from_file(args.cookies)
    else:
        cookies = parse_cookie_string(args.cookie_string)

    needed = ["c_user", "xs", "fr"]
    missing = [k for k in needed if k not in cookies]
    if missing:
        print(f"⚠️  Warning: Cookie {missing} tidak ada — mungkin tidak bisa login")
    else:
        print(f"✅ Cookies loaded ({len(cookies)} items)")
        print(f"   c_user: {cookies.get('c_user','?')}")

    # Jalankan flow
    flow = FacebookOAuthFlow(cookies, verbose=args.verbose)
    result = flow.run()

    if result:
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Disimpan ke: {args.output}")
        print("\n📋 Paste JSON ini ke bot Telegram setelah /login:")
        print(json.dumps(result))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
