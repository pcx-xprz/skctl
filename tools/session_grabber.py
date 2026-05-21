#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          Sky CoTL — Session Grabber v1.0                        ║
║          by skctl / artdeell Canvas reverse engineering         ║
╠══════════════════════════════════════════════════════════════════╣
║  MODE 1: Intercept via mitmproxy (HP + emulator)                ║
║  MODE 2: Auto OAuth via FB cookies dari browser                 ║
║  MODE 3: Manual paste JSON / JWT dari oauth_redirect            ║
╚══════════════════════════════════════════════════════════════════╝

Cara pakai:
  python session_grabber.py            → menu interaktif
  python session_grabber.py --mode 1   → mitmproxy proxy
  python session_grabber.py --mode 2   → FB cookie auto
  python session_grabber.py --mode 3   → manual input

Requirements:
  pip install requests mitmproxy
"""

import argparse
import json
import os
import re
import sys
import time
import threading
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import quote

# ── warna terminal ─────────────────────────────────────────────────────────────
R  = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
B  = "\033[94m"; M  = "\033[95m"; C  = "\033[96m"
W  = "\033[97m"; DIM = "\033[2m"; RESET = "\033[0m"; BOLD = "\033[1m"

SKY_BASE     = "https://live.radiance.thatgamecompany.com"
FB_BASE      = "https://web.facebook.com"
SKY_APP_ID   = "293746044767069"
REDIRECT_URI = f"{SKY_BASE}/account/auth/oauth_redirect"
STATE        = f"Facebook~{REDIRECT_URI}"
OUTPUT_FILE  = "sky_session_result.json"


def banner():
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════════╗
║      🌟  Sky CoTL Session Grabber  🌟                        ║
║         Reverse engineered from Canvas Open Source           ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


def save_result(data: dict, label: str = ""):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n{G}💾 Hasil disimpan ke: {OUTPUT_FILE}{RESET}")
    if data.get("session") and data.get("user_id"):
        print(f"\n{BOLD}{G}✅ SESSION BERHASIL!{RESET}")
        print(f"   {Y}user-id :{RESET} {data['user_id']}")
        print(f"   {Y}session :{RESET} {data['session'][:20]}...")
        print(f"\n{BOLD}📋 Copy-paste ke bot Telegram:{RESET}")
        print(f"   /session set {data['user_id']} {data['session']}")
    elif data.get("token"):
        print(f"\n{BOLD}{G}✅ TOKEN BERHASIL!{RESET}")
        print(f"   {Y}id    :{RESET} {data.get('id','?')}")
        print(f"   {Y}alias :{RESET} {data.get('alias','?')}")
        print(f"\n{BOLD}📋 Paste JSON ini ke bot Telegram setelah /login:{RESET}")
        print(f"   {json.dumps(data)}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — mitmproxy intercept
# ══════════════════════════════════════════════════════════════════════════════

MITM_ADDON = '''
"""Sky session interceptor — dipakai oleh session_grabber.py mode 1."""
import json, os
from datetime import datetime
from mitmproxy import http, ctx

TARGET_HOST = "live.radiance.thatgamecompany.com"
OUTPUT_FILE = "sky_session_result.json"

class SkyInterceptor:
    def __init__(self):
        self.captured = {}
        ctx.log.warn("🌟 Sky Session Interceptor AKTIF")
        ctx.log.warn(f"   Waiting for traffic to {TARGET_HOST}...")

    def request(self, flow: http.HTTPFlow):
        if TARGET_HOST not in flow.request.host:
            return
        h = dict(flow.request.headers)
        session  = h.get("session",  h.get("Session",  ""))
        user_id  = h.get("user-id",  h.get("User-Id",  ""))
        path     = flow.request.path

        if session and user_id:
            if user_id not in self.captured:
                self.captured[user_id] = {
                    "user_id":     user_id,
                    "session":     session,
                    "path":        path,
                    "captured_at": datetime.now().isoformat(),
                }
                with open(OUTPUT_FILE, "w") as f:
                    json.dump(self.captured[user_id], f, indent=2)
                ctx.log.warn("=" * 60)
                ctx.log.warn("✅ SKY SESSION CAPTURED!")
                ctx.log.warn(f"   user-id : {user_id}")
                ctx.log.warn(f"   session : {session[:20]}...")
                ctx.log.warn(f"   Disimpan ke {OUTPUT_FILE}")
                ctx.log.warn("=" * 60)
                ctx.log.warn(f"   /session set {user_id} {session}")

addons = [SkyInterceptor()]
'''


def run_mode1():
    """Mode 1: mitmproxy interceptor."""
    print(f"\n{BOLD}{C}── MODE 1: mitmproxy Interceptor ──{RESET}\n")

    # Simpan addon ke file temp
    addon_path = os.path.join(os.path.dirname(__file__), "_sky_addon.py")
    with open(addon_path, "w") as f:
        f.write(MITM_ADDON)

    # Cek mitmproxy terinstall
    try:
        import mitmproxy
    except ImportError:
        print(f"{Y}⚠️  mitmproxy belum terinstall. Install dulu:{RESET}")
        print(f"   pip install mitmproxy\n")
        _show_manual_mitm_guide()
        return

    port = 8080
    print(f"{G}✅ mitmproxy terinstall{RESET}")
    print(f"\n{BOLD}📋 Langkah-langkah:{RESET}")
    print(f"""
{Y}1.{RESET} Script akan jalankan proxy di port {BOLD}{port}{RESET}

{Y}2.{RESET} Di HP Android / Emulator:
   Settings → WiFi → Long press WiFi kamu → Modify Network
   → Advanced → Proxy → Manual
   → Server: {BOLD}[IP laptop kamu]{RESET}
   → Port  : {BOLD}{port}{RESET}

{Y}3.{RESET} Buka browser di HP → {BOLD}http://mitm.it{RESET}
   → Download & install certificate Android

{Y}4.{RESET} Buka game Sky → login dengan Facebook
   → Session akan otomatis ter-capture disini!

{DIM}(Tekan Ctrl+C untuk stop){RESET}
""")

    # Cek IP laptop
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"{G}🌐 IP laptop kamu: {BOLD}{local_ip}{RESET}")
        print(f"   Gunakan IP ini di pengaturan proxy HP\n")
    except Exception:
        print(f"{Y}⚠️  Tidak bisa detect IP otomatis — cek manual di Settings → WiFi{RESET}\n")

    input(f"{BOLD}Tekan ENTER untuk mulai mitmproxy...{RESET}")

    # Jalankan mitmproxy
    import subprocess
    cmd = [sys.executable, "-m", "mitmproxy",
           "-s", addon_path,
           "--listen-port", str(port),
           "--set", "ssl_insecure=true"]
    print(f"\n{G}▶ Menjalankan: {' '.join(cmd)}{RESET}\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n{Y}Proxy dihentikan.{RESET}")

    # Cek hasil
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            data = json.load(f)
        if data.get("session"):
            save_result(data, "mitmproxy")

    # Cleanup
    if os.path.exists(addon_path):
        os.remove(addon_path)


def _show_manual_mitm_guide():
    print(f"\n{BOLD}📋 Manual setup mitmproxy:{RESET}")
    print(f"""
  1. pip install mitmproxy
  2. mitmproxy -s sky_intercept.py --listen-port 8080
  3. Set proxy di HP → IP laptop, port 8080
  4. Buka mitm.it di HP → install cert
  5. Buka game Sky → login
""")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — FB Cookie automated OAuth
# ══════════════════════════════════════════════════════════════════════════════

def run_mode2():
    """Mode 2: Automated Facebook OAuth dari cookies browser."""
    import requests as rq

    print(f"\n{BOLD}{C}── MODE 2: Automated FB OAuth via Browser Cookies ──{RESET}\n")

    print(f"{BOLD}Cara export cookies dari browser Chrome:{RESET}")
    print(f"""
  {Y}1.{RESET} Install ekstensi: {BOLD}Cookie-Editor{RESET} atau {BOLD}EditThisCookie{RESET}
     Chrome: https://chrome.google.com/webstore/detail/cookie-editor
  
  {Y}2.{RESET} Buka {BOLD}web.facebook.com{RESET} → pastikan sudah login
  
  {Y}3.{RESET} Klik icon ekstensi → Export → Copy as JSON
  
  {Y}4.{RESET} Atau manual paste cookie string dari DevTools:
     F12 → Application → Cookies → web.facebook.com
     Copy nilai: {BOLD}c_user, xs, fr, datr, sb{RESET}
""")

    print(f"{BOLD}Pilih input method:{RESET}")
    print(f"  {Y}1{RESET} → Paste cookie string langsung (c_user=...; xs=...; ...)")
    print(f"  {Y}2{RESET} → Load dari file JSON")
    print(f"  {Y}3{RESET} → Kembali ke menu\n")

    choice = input(f"{BOLD}Pilihan [1/2/3]: {RESET}").strip()

    cookies = {}
    if choice == "1":
        print(f"\nPaste cookie string (contoh: c_user=123; xs=abc; fr=xyz):")
        print(f"{DIM}(Tekan Enter 2x setelah paste){RESET}")
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        cookie_str = " ".join(lines)
        for part in cookie_str.replace("\n", ";").split(";"):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                cookies[k.strip()] = v.strip()

    elif choice == "2":
        path = input("Path file cookies JSON: ").strip().strip('"')
        try:
            with open(path) as f:
                raw = json.load(f)
            if isinstance(raw, list):
                for item in raw:
                    k = item.get("name") or item.get("key", "")
                    v = item.get("value", "")
                    if k and v:
                        cookies[k] = v
            else:
                cookies = raw
            print(f"{G}✅ Loaded {len(cookies)} cookies dari {path}{RESET}")
        except Exception as e:
            print(f"{R}❌ Error: {e}{RESET}")
            return
    else:
        return

    # Validasi
    needed = ["c_user", "xs"]
    missing = [k for k in needed if k not in cookies]
    if missing:
        print(f"\n{R}❌ Cookie {missing} tidak ada — tidak bisa login FB{RESET}")
        print(f"   Pastikan export dari web.facebook.com yang sudah login")
        return

    print(f"\n{G}✅ Cookies valid: c_user={cookies.get('c_user','?')[:8]}...{RESET}")
    print(f"\n{BOLD}Menjalankan OAuth flow...{RESET}\n")

    # Buat session dengan cookies
    session = rq.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    })
    for k, v in cookies.items():
        session.cookies.set(k, v, domain=".facebook.com")

    # Step 1: Ambil fb_dtsg
    print(f"{DIM}⏳ Ambil fb_dtsg dari Facebook...{RESET}")
    try:
        r = session.get(FB_BASE + "/", timeout=15)
        dtsg = None
        for pat in [
            r'"DTSGInitialData".*?"token":"([^"]+)"',
            r'fb_dtsg.*?value="([^"]+)"',
            r'"fb_dtsg":"([^"]+)"',
        ]:
            m = re.search(pat, r.text)
            if m:
                dtsg = m.group(1)
                break
        if not dtsg:
            print(f"{R}❌ fb_dtsg tidak ditemukan — cookies mungkin expired{RESET}")
            return
        print(f"{G}✅ fb_dtsg: {dtsg[:20]}...{RESET}")
    except Exception as e:
        print(f"{R}❌ Error ambil fb_dtsg: {e}{RESET}")
        return

    # Step 2: POST games_service/save
    print(f"{DIM}⏳ Request OAuth authorization...{RESET}")
    logger_id = str(uuid.uuid4())
    url = (
        f"{FB_BASE}/v24.0/dialog/oauth/games_service/save/?"
        f"app_id={SKY_APP_ID}&"
        f"redirect_uri={quote(REDIRECT_URI)}&"
        f"state={quote(STATE)}&"
        f"response_type=code&"
        f"return_format[0]=code&return_scopes=false&"
        f"scope[0]=openid&scope[1]=gaming_profile&"
        f"display=page&seen_scopes[0]=openid&seen_scopes[1]=gaming_profile&"
        f"logger_id={logger_id}&is_new_user_flow=false&"
        f"app_vis=3&profile_type=gaming&tp=unspecified&is_limited_login_shim=false"
    )
    try:
        r2 = session.post(
            url,
            data={"fb_dtsg": dtsg},
            headers={
                "Content-Type":   "application/x-www-form-urlencoded",
                "Origin":         FB_BASE,
                "Referer":        f"{FB_BASE}/v24.0/dialog/oauth",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            },
            timeout=15,
            allow_redirects=False,
        )

        redirect_url = None
        loc = r2.headers.get("Location", "")
        if REDIRECT_URI.split("//")[1] in loc:
            redirect_url = loc
        else:
            m = re.search(r'content="0; URL=([^"]+)"', r2.text)
            if m:
                redirect_url = m.group(1).replace("&amp;", "&")
            else:
                m2 = re.search(r'code=([A-Za-z0-9_\-]+)', r2.text)
                if m2:
                    redirect_url = f"{REDIRECT_URI}?code={m2.group(1)}&state={quote(STATE)}"

        if not redirect_url:
            print(f"{R}❌ Tidak dapat redirect URL dari Facebook (status={r2.status_code}){RESET}")
            print(f"   Body: {r2.text[:300]}")
            return

        print(f"{G}✅ Dapat redirect URL dengan FB code!{RESET}")
    except Exception as e:
        print(f"{R}❌ Error request OAuth: {e}{RESET}")
        return

    # Step 3: Exchange code ke Sky
    print(f"{DIM}⏳ Exchange code ke Sky server...{RESET}")
    try:
        r3 = rq.get(
            redirect_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://web.facebook.com/"},
            timeout=15,
        )
        if r3.status_code == 200:
            data = r3.json()
            if data.get("token") and data.get("id"):
                result = {
                    "id":    data["id"],
                    "alias": data.get("alias", ""),
                    "token": data["token"],
                }
                save_result(result, "fb_oauth_auto")
                return
            print(f"{R}❌ Sky error: {data}{RESET}")
        else:
            print(f"{R}❌ Sky response {r3.status_code}: {r3.text[:200]}{RESET}")
    except Exception as e:
        print(f"{R}❌ Error exchange code: {e}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 3 — Manual input JSON / JWT
# ══════════════════════════════════════════════════════════════════════════════

def run_mode3():
    """Mode 3: Manual paste JSON atau JWT dari oauth_redirect."""
    import requests as rq

    print(f"\n{BOLD}{C}── MODE 3: Manual Input ──{RESET}\n")
    print(f"{BOLD}Langkah:{RESET}")
    print(f"""
  {Y}1.{RESET} Buka link ini di browser:
     {BOLD}https://live.radiance.thatgamecompany.com/account/auth/oauth_signin?type=Facebook&token={RESET}

  {Y}2.{RESET} Login dengan Facebook kamu

  {Y}3.{RESET} Setelah redirect, halaman akan tampil JSON:
     {BOLD}{{"id":"...","alias":"...","token":"eyJ..."}}{RESET}

  {Y}4.{RESET} Copy dan paste di bawah ini:
""")

    print("Paste JSON atau token (eyJ...) di sini:")
    print(f"{DIM}(Tekan Enter 2x setelah paste){RESET}")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    text = "".join(lines).strip()

    if not text:
        print(f"{R}❌ Tidak ada input{RESET}")
        return

    # Parse
    sky_id  = None
    alias   = None
    jwt_tok = None

    if text.startswith("{"):
        try:
            data = json.loads(text)
            jwt_tok = data.get("token") or data.get("access_token")
            sky_id  = data.get("id")
            alias   = data.get("alias")
        except Exception:
            pass
    elif text.startswith("eyJ"):
        jwt_tok = text

    if not jwt_tok:
        print(f"{R}❌ Format tidak dikenali{RESET}")
        return

    result = {
        "id":    sky_id or "",
        "alias": alias  or "",
        "token": jwt_tok,
    }
    save_result(result, "manual")

    print(f"\n{BOLD}📋 Paste JSON ini ke bot Telegram setelah /login:{RESET}")
    print(f"   {json.dumps(result)}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 4 — Emulator guide
# ══════════════════════════════════════════════════════════════════════════════

def run_mode4():
    """Mode 4: Panduan setup emulator Android + HTTP Toolkit."""
    print(f"\n{BOLD}{C}── MODE 4: Panduan Emulator Android ──{RESET}\n")
    print(f"""
{BOLD}Cara paling mudah mendapatkan Sky session di laptop:{RESET}

{Y}OPSI A — BlueStacks 5 (Direkomendasikan){RESET}
{DIM}─────────────────────────────────────────{RESET}
  1. Download BlueStacks 5: {BOLD}bluestacks.com{RESET}
     (Pastikan pilih BlueStacks 5 yang support ARM64)

  2. Download APK Sky dari: {BOLD}apkpure.com/sky-children-of-the-light{RESET}
     (Version terbaru, com.tgc.sky.android)

  3. Install APK di BlueStacks

  4. Download {BOLD}HTTP Toolkit{RESET}: {BOLD}httptoolkit.com{RESET}
     → Install di laptop (Windows/Mac/Linux, gratis)

  5. Buka HTTP Toolkit → klik {BOLD}"Android Emulator"{RESET}
     → Pilih BlueStacks → akan auto-setup proxy + certificate

  6. Buka Sky di BlueStacks → Login Facebook

  7. Di HTTP Toolkit, lihat request ke:
     {BOLD}live.radiance.thatgamecompany.com{RESET}
     → Cari header: {BOLD}session{RESET} dan {BOLD}user-id{RESET}

  8. Copy kedua nilai → paste ke bot:
     {BOLD}/session set <user-id> <session>{RESET}


{Y}OPSI B — Android x86 di VirtualBox (Advanced){RESET}
{DIM}──────────────────────────────────────────────{RESET}
  1. Download VirtualBox + Android x86 ISO
  2. Install Android di VM
  3. Setup proxy ke HTTP Toolkit di host
  4. Install Sky APK via adb


{Y}OPSI C — WSA Windows 11 (paling ringan){RESET}
{DIM}─────────────────────────────────────────{RESET}
  1. Enable Windows Subsystem for Android di Windows 11
     Settings → Optional Features → Windows Subsystem for Android
  2. Install Sky APK via adb: adb install sky.apk
  3. HTTP Toolkit → "Android Device via ADB"
  4. Done!


{Y}OPSI D — HP Android Langsung (100% berhasil){RESET}
{DIM}─────────────────────────────────────────────{RESET}
  1. Buka Sky di HP Android kamu (yang sudah install)
  2. HTTP Toolkit di laptop → "Android Device"
  3. Scan QR di HP → proxy + cert otomatis
  4. Login Sky → session ter-capture otomatis
  5. /session set <user-id> <session>


{BOLD}Semua method di atas menggunakan:{RESET}
  • HTTP Toolkit (gratis, httptoolkit.com)
  • atau mitmproxy (open source, run mode 1)
""")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def main_menu():
    banner()
    print(f"{BOLD}Pilih mode:{RESET}\n")
    print(f"  {C}1{RESET} → {BOLD}mitmproxy Interceptor{RESET}         "
          f"{DIM}(HP/emulator → proxy di laptop){RESET}")
    print(f"  {C}2{RESET} → {BOLD}Auto FB Cookie OAuth{RESET}           "
          f"{DIM}(export cookies dari browser Chrome){RESET}")
    print(f"  {C}3{RESET} → {BOLD}Manual Input JSON/JWT{RESET}          "
          f"{DIM}(paste response dari oauth_redirect){RESET}")
    print(f"  {C}4{RESET} → {BOLD}Panduan Emulator Android{RESET}       "
          f"{DIM}(BlueStacks/WSA + HTTP Toolkit){RESET}")
    print(f"  {C}0{RESET} → Keluar\n")

    choice = input(f"{BOLD}Pilihan [0-4]: {RESET}").strip()

    if   choice == "1": run_mode1()
    elif choice == "2": run_mode2()
    elif choice == "3": run_mode3()
    elif choice == "4": run_mode4()
    elif choice == "0": print(f"\n{DIM}Sampai jumpa!{RESET}"); sys.exit(0)
    else:
        print(f"{R}Pilihan tidak valid{RESET}")
        main_menu()


def main():
    parser = argparse.ArgumentParser(
        description="Sky CoTL Session Grabber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Mode:
  1  mitmproxy interceptor
  2  Automated FB cookie OAuth
  3  Manual JSON/JWT input
  4  Panduan emulator Android
        """,
    )
    parser.add_argument("--mode", "-m", type=int, choices=[1, 2, 3, 4],
                        help="Langsung jalankan mode tertentu")
    args = parser.parse_args()

    if args.mode == 1:   run_mode1()
    elif args.mode == 2: run_mode2()
    elif args.mode == 3: run_mode3()
    elif args.mode == 4: run_mode4()
    else:
        main_menu()


if __name__ == "__main__":
    main()
