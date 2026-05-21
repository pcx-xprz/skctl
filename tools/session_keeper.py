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
CHAT_ID     = os.environ.get("TELEGRAM_CHAT_ID", "")   # Telegram user ID kamu

# ── Pattern untuk capture session dari logcat ──────────────
# Sky v0.33+ pakai UUID format untuk session dan user-id
UUID_RE  = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
HEX32_RE = r'[0-9a-f]{32}'

PATTERNS = [
    # Format dari logcat nyata (sudah terbukti bekerja):
    # I/ (9305): X-Session-ID: 288f2870-5ad0-417d-bfaf-0e235bdb16e2
    (rf'X-Session-ID[:\s]+({UUID_RE})',           "session"),
    # I/ (9305): user_id  : 18a07aa9-b69d-485c-8856-122e06562e6c
    (rf'(?:user[_\-]?id|User-Id|user-id)[:\s]+"?({UUID_RE})',  "user_id"),
    # session header dalam HTTP request
    (rf'\bsession\b[:\s]+({UUID_RE})',             "session"),
    # hex32 session (format lama)
    (rf'\bsession\b[:\s]+({HEX32_RE})\b',         "session_hex"),
]

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
    Setiap kali ada session + user_id baru → auto kirim ke bot.
    """
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════╗
║          🔄  Sky Session Keeper — Auto Update           ║
╚══════════════════════════════════════════════════════════╝{RESET}

  Device  : {serial}
  Bot     : {'✅ Configured' if bot_token else '❌ Tidak ada — set TELEGRAM_BOT_TOKEN di .env'}
  Chat ID : {'✅ ' + chat_id if chat_id else '❌ Tidak ada — set TELEGRAM_CHAT_ID di .env'}

{Y}Cara pakai:{RESET}
  1. Script ini jalan terus di background
  2. Buka Sky di HP dan mainkan seperti biasa
  3. Setiap kali game connect ke server → session ter-capture
  4. Otomatis dikirim ke bot Telegram!

{DIM}Tekan Ctrl+C untuk stop{RESET}
""")

    if not bot_token or not chat_id:
        print(f"{Y}⚠️  Bot token/chat_id belum diset!{RESET}")
        print(f"   Session akan ditampilkan di terminal saja.")
        print(f"   Set di file .env:\n")
        print(f"   TELEGRAM_BOT_TOKEN=xxx")
        print(f"   TELEGRAM_CHAT_ID=xxx  {DIM}(angka, bukan username){RESET}\n")

    # Clear logcat dulu
    run_adb("-s", serial, "logcat", "-c")

    last_session = None
    last_user_id = None
    last_sent    = 0       # timestamp terakhir kirim
    COOLDOWN     = 30      # jangan kirim ulang dalam 30 detik

    found_session = {}     # {uuid: timestamp}
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
                        # Konversi hex32 ke UUID-like jika perlu
                        found_session[val] = time.time()
                        if val != last_session:
                            print(f"\n  {G}🔑 Session (hex): {val}{RESET}")

                    elif kind == "user_id":
                        found_user_id[val] = time.time()
                        if val != last_user_id:
                            print(f"\n  {G}👤 User ID: {val}{RESET}")

            # Coba match session + user_id
            # Ambil yang paling baru (dalam 30 detik terakhir)
            now = time.time()
            recent_sessions = [
                k for k, t in found_session.items() if now - t < 30
            ]
            recent_users = [
                k for k, t in found_user_id.items()
                if now - t < 30 and k not in recent_sessions  # user_id != session
            ]

            if recent_sessions and recent_users:
                new_session = recent_sessions[-1]
                new_user_id = recent_users[-1]

                # Hanya kirim jika berubah dan belum kirim baru-baru ini
                if (new_session != last_session or new_user_id != last_user_id) \
                        and (now - last_sent) > COOLDOWN:

                    last_session = new_session
                    last_user_id = new_user_id
                    last_sent    = now

                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"\n{G}{BOLD}╔═══════════════════════════════════════╗")
                    print(f"║  ✅ SESSION CAPTURED [{ts}]       ║")
                    print(f"╚═══════════════════════════════════════╝{RESET}")
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
