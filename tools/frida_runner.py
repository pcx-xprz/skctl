#!/usr/bin/env python3
"""
Sky CoTL Frida Runner
=====================
Script Python yang:
1. Cek frida-server di HP via ADB
2. Attach ke Sky process (butuh Canvas agar debuggable)
3. Inject frida_sky_hook.js
4. Terima session via RPC
5. Update sessions.json otomatis
6. Kirim notifikasi ke Telegram

REQUIREMENT:
  - Canvas terinstall di HP (https://github.com/artdeell/skymodloader)
  - Sky dijalankan MELALUI Canvas (bukan dari launcher biasa)
  - frida-server sudah di-push ke /data/local/tmp/frida-server
  - pip install frida frida-tools

CARA PAKAI:
  python tools/frida_runner.py

LOGIKA ALUR:
  HP (Sky via Canvas) ──── ADB ────► frida-server
                                          │
                               frida inject hook.js
                                          │
                              hook tangkap session header
                                          │
                              RPC kirim ke frida_runner.py
                                          │
                              update sessions.json
                                          │
                              bot Telegram bisa /cr
"""

import os
import sys
import json
import time
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
HERE         = Path(__file__).parent
PROJECT_ROOT = HERE.parent
HOOK_JS      = HERE / "frida_sky_hook.js"
SESSIONS_FILE = PROJECT_ROOT / "data" / "sessions.json"

# ── Load .env ──────────────────────────────────────────────────────────────────
def load_env():
    for path in [PROJECT_ROOT / ".env", HERE / ".env", Path(".env")]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break

load_env()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

SKY_PACKAGE    = "com.tgc.sky.android"
FRIDA_SERVER   = "/data/local/tmp/frida-server"
FRIDA_PORT     = 27042

# Warna terminal
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
C = "\033[96m"; DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


# ── ADB helpers ────────────────────────────────────────────────────────────────
def adb(*args) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["adb"] + list(args),
                           capture_output=True, text=True, timeout=15)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", "adb not found"
    except Exception as e:
        return -1, "", str(e)


def get_device() -> str | None:
    _, out, _ = adb("devices")
    for line in out.split("\n")[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def get_sky_pid() -> int | None:
    _, out, _ = adb("shell", "pidof", SKY_PACKAGE)
    out = out.strip()
    if out and out.isdigit():
        return int(out)
    return None


def start_frida_server(serial: str) -> bool:
    """Pastikan frida-server jalan di HP."""
    # Cek apakah sudah jalan
    _, out, _ = adb("-s", serial, "shell", "pidof", "frida-server")
    if out.strip():
        print(f"{G}✅ frida-server sudah jalan (PID {out.strip()}){RESET}")
        return True

    # Cek apakah file ada
    code, _, _ = adb("-s", serial, "shell", f"ls {FRIDA_SERVER}")
    if code != 0:
        print(f"{R}❌ frida-server tidak ada di {FRIDA_SERVER}{RESET}")
        print(f"""
{Y}Download frida-server dulu:{RESET}
  1. Cek arsitektur HP:
     adb shell getprop ro.product.cpu.abi
  
  2. Download dari:
     https://github.com/frida/frida/releases
     Pilih: frida-server-XX.X.X-android-arm64.xz
  
  3. Extract dan push:
     adb push frida-server /data/local/tmp/
     adb shell chmod 755 /data/local/tmp/frida-server
""")
        return False

    # Jalankan frida-server di background
    print(f"{DIM}Menjalankan frida-server...{RESET}")
    subprocess.Popen(
        ["adb", "-s", serial, "shell", f"{FRIDA_SERVER} &"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    # Verifikasi
    _, out, _ = adb("-s", serial, "shell", "pidof", "frida-server")
    if out.strip():
        print(f"{G}✅ frida-server berhasil dijalankan{RESET}")
        return True

    print(f"{R}❌ frida-server gagal dijalankan{RESET}")
    return False


# ── sessions.json ──────────────────────────────────────────────────────────────
def load_sessions() -> dict:
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_session(user_id: str, session: str) -> bool:
    """Update sessions.json dengan session baru."""
    try:
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = load_sessions()

        updated = False
        for tg_uid, info in data.items():
            if info.get("user_id") == user_id:
                info["session"] = session
                updated = True
                print(f"{G}✅ sessions.json updated untuk tg_uid={tg_uid}{RESET}")
                break

        if not updated:
            print(f"{Y}⚠️  user_id tidak ditemukan di sessions.json{RESET}")
            print(f"   Set manual dulu: /session set {user_id} {session}")
            return False

        with open(SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"{R}Error save session: {e}{RESET}")
        return False


# ── Telegram notification ──────────────────────────────────────────────────────
def notify(user_id: str, session: str, source: str = "frida"):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        msg = (
            f"🎯 <b>Session captured via {source}!</b>\n\n"
            f"🆔 user_id: <code>{user_id}</code>\n"
            f"🔑 session: <code>{session[:16]}...</code>\n\n"
            f"✅ sessions.json diupdate otomatis."
        )
        data = urllib.parse.urlencode({
            "chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"
        }).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data=data
            ), timeout=10
        )
    except Exception:
        pass


# ── Frida session ──────────────────────────────────────────────────────────────
def run_frida_hook(pid: int) -> dict | None:
    """
    Attach Frida ke Sky process, inject hook, tunggu session.
    
    LOGIKA:
    1. frida.attach(pid) → buka channel ke Sky process
    2. session.create_script(hook_js) → load hook ke memory Sky
    3. script.on('message', handler) → listen RPC callback
    4. Hook JS intercept OkHttp/SSL headers → kirim via send()
    5. Kita terima di handler → return session + user_id
    """
    try:
        import frida
    except ImportError:
        print(f"{R}❌ frida tidak terinstall!{RESET}")
        print(f"   pip install frida frida-tools")
        return None

    if not HOOK_JS.exists():
        print(f"{R}❌ {HOOK_JS} tidak ditemukan!{RESET}")
        return None

    hook_code = HOOK_JS.read_text(encoding="utf-8")

    captured = {}
    event    = threading.Event()

    def on_message(message, data):
        """Handler untuk pesan dari hook.js via send()."""
        if message["type"] == "send":
            payload = message.get("payload", {})
            msg_type = payload.get("type", "")

            print(f"\n{DIM}  [frida] {payload}{RESET}")

            # Tangkap session + user_id
            if msg_type == "session":
                session = payload.get("session", "")
                user_id = payload.get("user_id", "")
                if session and user_id:
                    captured["session"] = session
                    captured["user_id"] = user_id
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"\n{G}{BOLD}╔══════════════════════════════════════════╗")
                    print(f"║  🎯 SESSION CAPTURED via Frida [{ts}] ║")
                    print(f"╚══════════════════════════════════════════╝{RESET}")
                    print(f"  user_id : {user_id}")
                    print(f"  session : {session[:20]}...")
                    event.set()

            # Info dari SSL hook
            elif msg_type == "ssl_data":
                print(f"  {DIM}[SSL] {payload.get('preview', '')[:80]}{RESET}")

        elif message["type"] == "error":
            print(f"  {Y}[frida error] {message.get('description', '')}{RESET}")

    try:
        device  = frida.get_usb_device(timeout=5)
        session = device.attach(pid)
        script  = session.create_script(hook_code)
        script.on("message", on_message)
        script.load()

        print(f"{G}✅ Frida attached ke PID {pid}{RESET}")
        print(f"{G}✅ Hook JS loaded{RESET}")
        print(f"\n{Y}Sekarang buka Sky dan lakukan aksi apapun (masuk realm, dll){RESET}")
        print(f"{DIM}Menunggu session... (Ctrl+C untuk cancel){RESET}\n")

        # Coba RPC langsung untuk session yang sudah ada
        try:
            result = script.exports.get_session()
            if result and result.get("session") and result.get("user_id"):
                print(f"{G}✅ Session sudah ada di memory!{RESET}")
                captured.update(result)
                event.set()
        except Exception:
            pass  # Session belum ada, tunggu via hook

        # Tunggu sampai session dicapture (max 3 menit)
        event.wait(timeout=180)

        script.unload()
        session.detach()

        return captured if captured else None

    except frida.ProcessNotFoundError:
        print(f"{R}❌ Sky process tidak ditemukan (PID {pid}){RESET}")
        print(f"   Pastikan Sky dijalankan via Canvas!")
        return None
    except frida.PermissionDeniedError:
        print(f"{R}❌ Permission denied!{RESET}")
        print(f"""
{Y}Kemungkinan penyebab:{RESET}
  1. Sky tidak dijalankan via Canvas
     → Canvas otomatis set android:debuggable=true
     → Tanpa Canvas, Frida tidak bisa attach
  
  2. Canvas belum terinstall
     → Download: https://github.com/artdeell/skymodloader/releases
     → Install, buka Sky dari dalam Canvas
""")
        return None
    except Exception as e:
        print(f"{R}❌ Frida error: {e}{RESET}")
        return None


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════╗
║          🎯  Sky Frida Session Runner                   ║
║          Powered by Canvas + Frida                      ║
╚══════════════════════════════════════════════════════════╝{RESET}

{BOLD}LOGIKA:{RESET}
  1. ADB connect ke HP
  2. Start frida-server di HP  
  3. Attach ke Sky process (butuh Canvas!)
  4. Inject hook → intercept HTTP headers
  5. Capture session + user_id
  6. Update sessions.json → bot bisa /cr

{BOLD}REQUIREMENT:{RESET}
  {Y}●{RESET} Canvas terinstall di HP
  {Y}●{RESET} Sky dijalankan VIA Canvas (bukan dari launcher biasa)
  {Y}●{RESET} frida-server ada di /data/local/tmp/frida-server
  {Y}●{RESET} pip install frida frida-tools
""")

    # 1. Cek ADB
    _, out, _ = adb("version")
    if not out:
        print(f"{R}❌ ADB tidak ditemukan!{RESET}")
        sys.exit(1)

    # 2. Cek device
    serial = get_device()
    if not serial:
        print(f"{R}❌ Tidak ada device ADB!{RESET}")
        sys.exit(1)
    print(f"{G}✅ Device: {serial}{RESET}")

    # 3. Start frida-server
    if not start_frida_server(serial):
        sys.exit(1)

    # 4. Cek apakah Sky jalan
    print(f"\n{DIM}Mencari Sky process...{RESET}")
    pid = None
    for attempt in range(10):
        pid = get_sky_pid()
        if pid:
            break
        if attempt == 0:
            print(f"{Y}Sky belum terbuka. Buka Sky via Canvas di HP...{RESET}")
        time.sleep(3)

    if not pid:
        print(f"{R}❌ Sky tidak ditemukan setelah 30 detik{RESET}")
        print(f"   Pastikan Sky dijalankan via Canvas!")
        sys.exit(1)

    print(f"{G}✅ Sky PID: {pid}{RESET}")

    # 5. Frida hook
    print(f"\n{DIM}Memulai Frida hook...{RESET}")
    result = run_frida_hook(pid)

    if not result or not result.get("session"):
        print(f"\n{Y}⚠️  Session tidak ter-capture.{RESET}")
        print(f"   Coba lagi setelah Sky benar-benar login.")
        sys.exit(1)

    user_id = result["user_id"]
    session = result["session"]

    # 6. Update sessions.json
    print(f"\n{DIM}Menyimpan session...{RESET}")
    ok = save_session(user_id, session)

    # 7. Notifikasi Telegram
    notify(user_id, session, source="Frida+Canvas")

    # 8. Summary
    print(f"""
{G}{BOLD}╔══════════════════════════════════════════════════════════╗
║              ✅ BERHASIL!                               ║
╚══════════════════════════════════════════════════════════╝{RESET}

  user_id : {user_id}
  session : {session[:20]}...
  file    : {SESSIONS_FILE}

{BOLD}Sekarang di bot Telegram:{RESET}
  /account  → lihat data akun
  /wax      → lihat wax balance  
  /cr       → auto candle run
  /forge    → forge wax → candles
""")

    if not ok:
        print(f"{Y}⚠️  Set manual karena user_id belum ada di sessions.json:{RESET}")
        print(f"  /session set {user_id} {session}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}Cancelled.{RESET}")
