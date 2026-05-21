#!/usr/bin/env python3
"""
Sky Session Keeper
==================
Monitor logcat TERUS-MENERUS dan auto-update session ke bot Telegram
setiap kali Sky game melakukan request ke server.

Cara pakai:
  1. Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di bawah
     (atau buat file .env di folder skctl/)
  2. Colok HP, aktifkan USB Debugging
  3. Buka Sky di HP
  4. Jalankan script ini:
     python tools/session_keeper.py

Script akan:
  - Monitor logcat terus-menerus
  - Setiap kali ada session baru → langsung kirim /session set ke bot
  - Kamu tidak perlu lakukan apa-apa lagi!
"""

import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import json
import argparse
from datetime import datetime

# ── Load .env jika ada ─────────────────────────────────────
def load_env():
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
        ".env",
    ]
    for path in env_paths:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break

load_env()

BOT_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID     = os.environ.get("TELEGRAM_CHAT_ID", "")   # Telegram user ID kamu (angka)

# ── Pattern untuk capture session dari logcat ──────────────
UUID_RE  = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
HEX32_RE = r'[0-9a-f]{32}'

PATTERNS = [
    # X-Session-ID header (terbukti muncul di Sky v0.33 logcat)
    # I/ (14833): X-Session-ID: 3407977f-f19e-430a-9c62-20daa774cbca
    (rf'X-Session-ID[:\s]+({UUID_RE})',                         "session"),
    # user-id header (kadang muncul)
    (rf'(?:user[_\-]?id|User-Id|user-id|X-User-ID)[:\s]+"?({UUID_RE})',  "user_id"),
    # session header generic
    (rf'\bsession\b[:\s]+({UUID_RE})',                          "session"),
    # hex32 session
    (rf'\bsession\b[:\s]+({HEX32_RE})\b',                      "session_hex"),
]

def load_saved_user_id() -> str | None:
    """
    Load user_id dari sessions.json yang sudah tersimpan.
    Karena Sky v0.33 tidak log user-id di logcat,
    kita pakai user_id yang sudah pernah di-set manual sebelumnya.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sessions_path = os.path.join(here, "data", "sessions.json")
    if not os.path.exists(sessions_path):
        return None
    try:
        with open(sessions_path) as f:
            data = json.load(f)
        for tg_uid, info in data.items():
            uid = info.get("user_id")
            if uid:
                print(f"{G}✅ user_id dari sessions.json: {uid}{RESET}")
                return uid
    except Exception as e:
        print(f"{Y}Tidak bisa baca sessions.json: {e}{RESET}")
    return None

# Warna terminal
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
C = "\033[96m"; DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """Kirim pesan ke Telegram."""
    if not bot_token or not chat_id:
        return False
    try:
        url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "HTML",
        }).encode()
        req  = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"{R}Telegram error: {e}{RESET}")
        return False


def auto_set_session(bot_token: str, chat_id: str, user_id: str, session: str) -> bool:
    """Kirim /session set ke bot."""
    msg = f"/session set {user_id} {session}"
    ok  = send_telegram(bot_token, chat_id, msg)
    if ok:
        print(f"{G}✅ Session dikirim ke bot!{RESET}")
    return ok


def run_adb(*args) -> tuple:
    try:
        result = subprocess.run(
            ["adb"] + list(args),
            capture_output=True, text=True, timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "adb not found"
    except Exception as e:
        return -1, "", str(e)


def get_device() -> str | None:
    code, out, _ = run_adb("devices")
    for line in out.split("\n")[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def monitor_logcat(serial: str, bot_token: str, chat_id: str):
    """
    Monitor logcat terus-menerus.
    Setiap kali ada session baru → auto kirim ke bot.
    Sky v0.33 hanya emit X-Session-ID, bukan user-id.
    user_id diambil dari sessions.json yang sudah tersimpan.
    """
    # Load user_id dari sessions.json (tidak berubah antar sesi)
    saved_user_id = load_saved_user_id()

    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════╗
║          🔄  Sky Session Keeper — Auto Update           ║
╚══════════════════════════════════════════════════════════╝{RESET}

  Device   : {serial}
  Bot      : {'✅ Configured' if bot_token else '❌ Tidak ada — set TELEGRAM_BOT_TOKEN di .env'}
  Chat ID  : {'✅ ' + chat_id if chat_id else '❌ Tidak ada — set TELEGRAM_CHAT_ID di .env'}
  user_id  : {'✅ ' + saved_user_id if saved_user_id else '⚠️  Belum ada — set dulu via /session set di bot'}

{Y}Cara pakai:{RESET}
  1. Script ini jalan terus di background
  2. Buka Sky di HP dan mainkan seperti biasa
  3. Setiap kali game connect ke server → session ter-capture
  4. Otomatis dikirim ke bot Telegram!

{DIM}Tekan Ctrl+C untuk stop{RESET}
""")

    if not bot_token or not chat_id:
        print(f"{Y}⚠️  Bot token/chat_id belum diset!{RESET}")
        print(f"   Set di file .env:")
        print(f"   TELEGRAM_BOT_TOKEN=<token_bot>")
        print(f"   TELEGRAM_CHAT_ID=7506302538  {DIM}(user ID kamu, bukan bot ID){RESET}\n")

    if not saved_user_id:
        print(f"{Y}⚠️  user_id belum tersimpan!{RESET}")
        print(f"   Set dulu sekali saja di bot Telegram:")
        print(f"   /session set <user_id> <session_id_apapun>\n")

    # Clear logcat dulu
    run_adb("-s", serial, "logcat", "-c")

    last_session = None
    last_user_id = saved_user_id  # pakai user_id dari file
    last_sent    = 0
    COOLDOWN     = 30

    found_session = {}
    found_user_id = {}

    print(f"{G}▶ Monitoring logcat... Buka/gunakan Sky di HP{RESET}\n")

    try:
        proc = subprocess.Popen(
            ["adb", "-s", serial, "logcat", "-v", "brief", "*:V"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True, errors="replace",
        )

        while True:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.01)
                continue

            lower = line.lower()

            # Filter hanya baris yang relevan
            if not any(kw in lower for kw in [
                "session", "user_id", "user-id", "userid",
                "radiance", "tgc.sky", "sky-live"
            ]):
                continue

            # Print baris yang relevan
            print(f"  {DIM}{line.rstrip()[:140]}{RESET}")

            # Cari patterns
            for pat, kind in PATTERNS:
                for m in re.finditer(pat, line, re.IGNORECASE):
                    val = m.group(1).lower()

                    if kind == "session":
                        found_session[val] = time.time()
                        if val != last_session:
                            print(f"\n  {G}🔑 Session baru: {val}{RESET}")

                    elif kind == "session_hex":
                        found_session[val] = time.time()
                        if val != last_session:
                            print(f"\n  {G}🔑 Session (hex): {val}{RESET}")

                    elif kind == "user_id":
                        found_user_id[val] = time.time()
                        if val != last_user_id:
                            print(f"\n  {G}👤 User ID dari logcat: {val}{RESET}")
                            last_user_id = val  # update user_id jika ketemu di logcat

            # Coba kirim session jika ada
            now = time.time()
            recent_sessions = [
                k for k, t in found_session.items() if now - t < 30
            ]

            # user_id: dari logcat atau dari sessions.json
            recent_users = [
                k for k, t in found_user_id.items()
                if now - t < 30 and k not in recent_sessions
            ]
            effective_user_id = (recent_users[-1] if recent_users
                                  else last_user_id)  # fallback ke user_id tersimpan

            if recent_sessions and effective_user_id:
                new_session = recent_sessions[-1]
                new_user_id = effective_user_id

                if new_session != last_session and (now - last_sent) > COOLDOWN:
                    last_session = new_session
                    last_sent    = now

                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"\n{G}{BOLD}╔═══════════════════════════════════════════╗")
                    print(f"║  ✅ SESSION CAPTURED [{ts}]         ║")
                    print(f"╚═══════════════════════════════════════════╝{RESET}")
                    print(f"  user_id : {new_user_id}")
                    print(f"  session : {new_session[:20]}...")

                    if bot_token and chat_id:
                        print(f"\n  {DIM}Mengirim ke bot...{RESET}")
                        ok = auto_set_session(bot_token, chat_id, new_user_id, new_session)
                        if ok:
                            print(f"  {G}✅ Bot sudah update! Coba /account di Telegram.{RESET}\n")
                        else:
                            print(f"  {Y}⚠️  Gagal kirim ke bot. Set manual:{RESET}")
                            print(f"  /session set {new_user_id} {new_session}\n")
                    else:
                        print(f"\n  {Y}Kirim manual ke bot:{RESET}")
                        print(f"  {BOLD}/session set {new_user_id} {new_session}{RESET}\n")

            elif recent_sessions and not effective_user_id:
                # Punya session tapi tidak punya user_id
                new_session = recent_sessions[-1]
                if new_session != last_session:
                    last_session = new_session
                    print(f"\n{Y}⚠️  Session ter-capture tapi user_id belum ada!{RESET}")
                    print(f"  session : {new_session}")
                    print(f"  {Y}Set user_id dulu di bot:{RESET}")
                    print(f"  /session set <user_id_kamu> {new_session}")
                    print(f"  {DIM}(user_id adalah UUID dari logcat sebelumnya){RESET}\n")

    except KeyboardInterrupt:
        print(f"\n{Y}Stopped.{RESET}")
        if last_session and last_user_id:
            print(f"\nSession terakhir yang dicapture:")
            print(f"  /session set {last_user_id} {last_session}")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def get_chat_id(bot_token: str) -> str | None:
    """Auto-detect chat_id dari getUpdates (user harus sudah pernah chat dengan bot)."""
    try:
        url  = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        req  = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        results = data.get("result", [])
        if results:
            # Ambil chat_id dari pesan terakhir
            msg = results[-1]
            chat_id = (
                msg.get("message", {}).get("chat", {}).get("id") or
                msg.get("callback_query", {}).get("message", {}).get("chat", {}).get("id")
            )
            if chat_id:
                return str(chat_id)
    except Exception as e:
        print(f"getUpdates error: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Sky Session Keeper — Auto update session ke bot")
    parser.add_argument("--serial",  "-s", help="Serial ADB device")
    parser.add_argument("--token",   "-t", help="Telegram bot token")
    parser.add_argument("--chat-id", "-c", help="Telegram chat ID (angka)")
    args = parser.parse_args()

    bot_token = args.token   or BOT_TOKEN
    chat_id   = args.chat_id or CHAT_ID

    # Auto-detect chat_id jika belum ada
    if bot_token and not chat_id:
        print(f"{DIM}Auto-detect chat_id dari bot...{RESET}")
        chat_id = get_chat_id(bot_token)
        if chat_id:
            print(f"{G}✅ Chat ID: {chat_id}{RESET}")
        else:
            print(f"{Y}⚠️  Tidak bisa auto-detect chat_id.{RESET}")
            print(f"   Kirim pesan apapun ke bot dulu, lalu jalankan script ini lagi.")
            print(f"   Atau set TELEGRAM_CHAT_ID di .env\n")

    # Cek ADB
    code, out, _ = run_adb("version")
    if code != 0:
        print(f"{R}❌ ADB tidak ditemukan! Install dulu.{RESET}")
        sys.exit(1)

    # Cari device
    serial = args.serial
    if not serial:
        serial = get_device()
        if not serial:
            print(f"{R}❌ Tidak ada device ADB!{RESET}")
            print(f"   Colok HP via USB dan aktifkan USB Debugging.")
            sys.exit(1)

    monitor_logcat(serial, bot_token, chat_id)


if __name__ == "__main__":
    main()
