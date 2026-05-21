#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║       Sky CoTL — ADB Session Grabber                        ║
║       Grab session langsung dari HP via USB Debug           ║
╠══════════════════════════════════════════════════════════════╣
║  CARA PAKAI:                                                ║
║  1. Aktifkan USB Debugging di HP                            ║
║  2. Colok HP ke laptop via USB                              ║
║  3. Jalankan: python adb_session_grabber.py                 ║
╚══════════════════════════════════════════════════════════════╝

Requirements:
  pip install requests
  
ADB:
  Windows: https://developer.android.com/tools/releases/platform-tools
  Mac:     brew install android-platform-tools
  Linux:   sudo apt install adb
"""

import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

# ── warna terminal ─────────────────────────────────────────
R    = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
B    = "\033[94m"; C  = "\033[96m"; W  = "\033[97m"
DIM  = "\033[2m";  BOLD = "\033[1m"; RESET = "\033[0m"

# ── Sky package names ───────────────────────────────────────
SKY_PACKAGES = [
    "com.tgc.sky.android",
    "com.tgc.sky.vn.android",
    "com.tgc.sky.android.huawei",
]

OUTPUT_FILE = "sky_session_result.json"


def banner():
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════╗
║        🔌  Sky CoTL ADB Session Grabber  🔌              ║
║        Grab session langsung dari HP via USB Debug       ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")


def run_adb(*args, device: str = None) -> tuple[int, str, str]:
    """Jalankan perintah adb, return (returncode, stdout, stderr)."""
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += list(args)
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "adb not found"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def check_adb() -> bool:
    """Cek apakah adb terinstall."""
    code, out, err = run_adb("version")
    if code != 0:
        print(f"{R}❌ ADB tidak ditemukan!{RESET}")
        print(f"""
{BOLD}Install ADB dulu:{RESET}

  {Y}Windows:{RESET} 
    Download: https://developer.android.com/tools/releases/platform-tools
    Extract → tambah ke PATH

  {Y}Mac:{RESET}
    brew install android-platform-tools

  {Y}Linux:{RESET}
    sudo apt install adb
    # atau
    sudo dnf install android-tools

  {Y}Setelah install, jalankan script ini lagi.{RESET}
""")
        return False
    
    version_match = re.search(r"version ([\d.]+)", out)
    version = version_match.group(1) if version_match else "?"
    print(f"{G}✅ ADB ditemukan — version {version}{RESET}")
    return True


def get_devices() -> list[dict]:
    """Ambil daftar device yang terhubung."""
    code, out, err = run_adb("devices", "-l")
    devices = []
    
    for line in out.split("\n")[1:]:  # Skip header
        line = line.strip()
        if not line or "offline" in line or "unauthorized" in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            info = {"serial": parts[0], "details": " ".join(parts[2:])}
            devices.append(info)
    
    return devices


def wait_for_device() -> Optional[str]:
    """Tunggu HP terhubung dan authorized."""
    print(f"\n{BOLD}📱 Menunggu HP terhubung...{RESET}")
    print(f"{DIM}  Pastikan:{RESET}")
    print(f"  {Y}1.{RESET} USB Debugging aktif di HP")
    print(f"     Settings → Developer Options → USB Debugging ✓")
    print(f"  {Y}2.{RESET} Colok HP ke laptop via USB")
    print(f"  {Y}3.{RESET} Tap 'Allow USB Debugging' di HP jika ada popup")
    print()
    
    for i in range(30):  # tunggu max 30 detik
        devices = get_devices()
        if devices:
            dev = devices[0]
            print(f"{G}✅ HP terhubung: {dev['serial']} {dev['details']}{RESET}")
            return dev['serial']
        
        # Cek unauthorized
        code, out, _ = run_adb("devices")
        if "unauthorized" in out:
            print(f"\r{Y}⚠️  HP terdeteksi tapi belum authorize. "
                  f"Tap 'Allow' di HP!{RESET}      ", end="", flush=True)
        else:
            print(f"\r{DIM}⏳ Menunggu... ({i+1}/30){RESET}      ", end="", flush=True)
        time.sleep(1)
    
    print(f"\n{R}❌ Timeout — HP tidak terdeteksi{RESET}")
    return None


def find_sky_package(serial: str) -> Optional[str]:
    """Cari package Sky yang terinstall di HP."""
    print(f"\n{DIM}🔍 Mencari Sky di HP...{RESET}")
    
    for pkg in SKY_PACKAGES:
        code, out, _ = run_adb("shell", "pm", "list", "packages", pkg, device=serial)
        if f"package:{pkg}" in out:
            print(f"  {G}✅ Ditemukan: {pkg}{RESET}")
            return pkg
    
    # Cari lebih luas
    code, out, _ = run_adb("shell", "pm", "list", "packages", "tgc.sky", device=serial)
    matches = re.findall(r"package:([\w.]+)", out)
    if matches:
        pkg = matches[0]
        print(f"  {G}✅ Ditemukan: {pkg}{RESET}")
        return pkg
    
    print(f"  {R}❌ Sky tidak terinstall di HP ini{RESET}")
    print(f"     Install dulu dari Play Store: Sky: Children of the Light")
    return None


def grab_session_methods(serial: str, package: str) -> Optional[dict]:
    """
    Coba semua metode untuk grab session dari Sky.
    
    Metode yang dicoba (urutan dari termudah ke susah):
    1. SharedPreferences (data/data/<package>/shared_prefs/)
    2. SQLite database
    3. Logcat (login saat script jalan)
    4. /proc/net (network connections)
    5. Memory dump (butuh root)
    """
    
    print(f"\n{BOLD}🔍 Mulai grab session...{RESET}\n")
    
    # ── Metode 1: SharedPreferences ────────────────────────────────────────────
    print(f"{C}[1/5]{RESET} Cek SharedPreferences...")
    result = _method_shared_prefs(serial, package)
    if result:
        return result
    
    # ── Metode 2: SQLite ───────────────────────────────────────────────────────
    print(f"{C}[2/5]{RESET} Cek SQLite databases...")
    result = _method_sqlite(serial, package)
    if result:
        return result
    
    # ── Metode 3: Files di app data dir ───────────────────────────────────────
    print(f"{C}[3/5]{RESET} Cek files di app data...")
    result = _method_app_files(serial, package)
    if result:
        return result
    
    # ── Metode 4: Logcat (intercept saat login) ────────────────────────────────
    print(f"{C}[4/5]{RESET} Monitor logcat untuk session...")
    result = _method_logcat(serial, package)
    if result:
        return result
    
    # ── Metode 5: Memory (butuh root) ─────────────────────────────────────────
    print(f"{C}[5/5]{RESET} Coba memory dump (butuh root)...")
    result = _method_memory(serial, package)
    if result:
        return result
    
    return None


def _method_shared_prefs(serial: str, package: str) -> Optional[dict]:
    """Cek SharedPreferences di /data/data/<pkg>/shared_prefs/"""
    
    # List shared_prefs
    code, out, err = run_adb(
        "shell", "run-as", package,
        "ls", f"/data/data/{package}/shared_prefs/",
        device=serial
    )
    
    if code != 0 or not out:
        # Coba tanpa run-as (emulator biasanya bisa)
        code, out, err = run_adb(
            "shell", "ls", f"/data/data/{package}/shared_prefs/",
            device=serial
        )
    
    if code != 0 or not out:
        print(f"  {DIM}→ SharedPreferences tidak accessible (butuh run-as/root){RESET}")
        return None
    
    files = out.strip().split("\n")
    print(f"  {G}Found {len(files)} preference files{RESET}")
    
    # Baca setiap file
    keywords = ["session", "user_id", "user-id", "userId", "account", "auth", "token"]
    
    for fname in files:
        fname = fname.strip()
        if not fname.endswith(".xml"):
            continue
        
        # Coba baca dengan run-as
        for cmd_prefix in [["run-as", package], []]:
            code, content, _ = run_adb(
                "shell", *cmd_prefix,
                "cat", f"/data/data/{package}/shared_prefs/{fname}",
                device=serial
            )
            if code == 0 and content:
                break
        
        if not content:
            continue
        
        # Cari session & user_id di XML
        session_match = re.search(
            r'name="session[^"]*"[^>]*>([^<]+)', content, re.IGNORECASE
        )
        userid_match  = re.search(
            r'name="(?:user.?id|userId|account.?id)[^"]*"[^>]*>([^<]+)',
            content, re.IGNORECASE
        )
        
        if session_match or userid_match:
            session = session_match.group(1).strip() if session_match else None
            user_id = userid_match.group(1).strip()  if userid_match  else None
            
            print(f"  {G}✅ Ditemukan di {fname}!{RESET}")
            if session: print(f"     session : {session[:20]}...")
            if user_id: print(f"     user-id : {user_id}")
            
            if session and user_id:
                return {"user_id": user_id, "session": session, "source": fname}
        
        # Cari pola session hex (32 char hex)
        hex_sessions = re.findall(r'>[0-9a-f]{32,64}<', content)
        if hex_sessions:
            print(f"  {Y}  Possible session hex di {fname}: {hex_sessions[0][:20]}...{RESET}")
    
    return None


def _method_sqlite(serial: str, package: str) -> Optional[dict]:
    """Cek SQLite databases."""
    
    code, out, _ = run_adb(
        "shell", "find", f"/data/data/{package}/",
        "-name", "*.db", "-o", "-name", "*.sqlite",
        device=serial
    )
    
    if code != 0 or not out:
        # Coba dengan run-as
        code, out, _ = run_adb(
            "shell", "run-as", package,
            "find", f"/data/data/{package}/",
            "-name", "*.db",
            device=serial
        )
    
    if not out:
        print(f"  {DIM}→ Tidak ada SQLite database accessible{RESET}")
        return None
    
    dbs = [d.strip() for d in out.split("\n") if d.strip()]
    print(f"  Found {len(dbs)} database(s)")
    
    for db in dbs:
        # Query dengan sqlite3
        for tbl_cmd in [
            f"sqlite3 {db} '.tables'",
            f"sqlite3 {db} 'SELECT * FROM accounts LIMIT 5'",
            f"sqlite3 {db} 'SELECT * FROM session LIMIT 5'",
        ]:
            code, out, _ = run_adb(
                "shell", "run-as", package, tbl_cmd,
                device=serial
            )
            if code == 0 and out:
                # Cari session pattern
                hex_match = re.search(r'[0-9a-f]{32,}', out)
                uuid_match = re.search(
                    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                    out
                )
                if hex_match or uuid_match:
                    print(f"  {G}Interesting data in {os.path.basename(db)}: {out[:100]}{RESET}")
    
    return None


def _method_app_files(serial: str, package: str) -> Optional[dict]:
    """Cek files di app data directory."""
    
    dirs = [
        f"/data/data/{package}/files/",
        f"/data/data/{package}/cache/",
        f"/sdcard/Android/data/{package}/files/",
    ]
    
    for data_dir in dirs:
        code, out, _ = run_adb(
            "shell", "find", data_dir,
            "-type", "f", "-name", "*.json",
            device=serial
        )
        if code == 0 and out:
            for fpath in out.strip().split("\n"):
                fpath = fpath.strip()
                if not fpath:
                    continue
                code2, content, _ = run_adb("shell", "cat", fpath, device=serial)
                if code2 == 0 and content:
                    # Cari session/user_id
                    if re.search(r'"session"', content, re.IGNORECASE):
                        print(f"  {G}✅ Session data di {fpath}!{RESET}")
                        try:
                            data = json.loads(content)
                            session = data.get("session") or data.get("Session")
                            user_id = data.get("user_id") or data.get("userId") or data.get("user-id")
                            if session and user_id:
                                return {"user_id": user_id, "session": session, "source": fpath}
                        except Exception:
                            pass
    
    print(f"  {DIM}→ Tidak ada session file ditemukan{RESET}")
    return None


def _method_logcat(serial: str, package: str) -> Optional[dict]:
    """Monitor logcat untuk menangkap session saat login."""
    
    print(f"""
  {BOLD}📋 Logcat Monitor Mode{RESET}
  
  {Y}Langkah:{RESET}
  1. Script akan monitor logcat HP kamu
  2. {BOLD}Buka Sky di HP → Login Facebook{RESET}
  3. Session akan otomatis ter-capture!
  
  {DIM}(Tekan Ctrl+C untuk skip metode ini){RESET}
""")
    
    input(f"  Tekan ENTER untuk mulai monitor logcat...")
    
    print(f"\n  {G}▶ Monitoring logcat... (buka Sky dan login sekarang!){RESET}")
    print(f"  {DIM}Ctrl+C untuk skip{RESET}\n")
    
    # Clear logcat dulu
    run_adb("logcat", "-c", device=serial)
    
    # Pattern yang dicari
    session_patterns = [
        r'session["\s:=]+([0-9a-f]{16,})',
        r'user.?id["\s:=]+"?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        r'"session"\s*:\s*"([^"]{16,})"',
        r'"user.?id"\s*:\s*"([^"]{8,})"',
        r'X-Session[:\s]+([0-9a-f]{16,})',
    ]
    
    session = None
    user_id = None
    
    try:
        proc = subprocess.Popen(
            ["adb", "-s", serial, "logcat", "-v", "tag",
             f"{package}:V", "Sky:V", "*:S"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        start = time.time()
        timeout = 120  # 2 menit
        
        while time.time() - start < timeout:
            line = proc.stdout.readline()
            if not line:
                continue
            
            # Print baris yang relevan
            if any(kw in line.lower() for kw in
                   ["session", "user_id", "userid", "login", "auth", "account"]):
                print(f"  {DIM}{line.strip()}{RESET}")
            
            # Cari session
            for pat in session_patterns:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    val = m.group(1)
                    if "session" in pat.lower() and not session:
                        session = val
                        print(f"\n  {G}✅ Session ditemukan: {val[:20]}...{RESET}")
                    elif "user" in pat.lower() and not user_id:
                        user_id = val
                        print(f"\n  {G}✅ User-ID ditemukan: {val}{RESET}")
            
            if session and user_id:
                proc.terminate()
                return {"user_id": user_id, "session": session, "source": "logcat"}
        
        proc.terminate()
        
    except KeyboardInterrupt:
        print(f"\n  {Y}Logcat monitoring dihentikan{RESET}")
        return None
    
    if session or user_id:
        print(f"\n  {Y}Data parsial:{RESET}")
        if session: print(f"    session: {session}")
        if user_id: print(f"    user_id: {user_id}")
    else:
        print(f"\n  {DIM}Tidak ada session ditemukan via logcat{RESET}")
    
    return None


def _method_memory(serial: str, package: str) -> Optional[dict]:
    """Coba dump memory process Sky (butuh root)."""
    
    # Cek root
    code, out, _ = run_adb("shell", "id", device=serial)
    is_root = "uid=0" in out or "root" in out.lower()
    
    if not is_root:
        # Coba su
        code, out, _ = run_adb("shell", "su", "-c", "id", device=serial)
        is_root = "uid=0" in out
    
    if not is_root:
        print(f"  {DIM}→ HP tidak di-root, skip memory dump{RESET}")
        return None
    
    print(f"  {G}✅ Root terdeteksi! Mencoba memory dump...{RESET}")
    
    # Cari PID Sky
    code, out, _ = run_adb("shell", "pgrep", "-f", package, device=serial)
    if not out:
        print(f"  {Y}  Sky tidak berjalan, buka dulu lalu jalankan script ini lagi{RESET}")
        return None
    
    pid = out.strip().split("\n")[0].strip()
    print(f"  Sky PID: {pid}")
    
    # Dump maps untuk cari region yang relevan
    code, maps, _ = run_adb(
        "shell", "su", "-c", f"cat /proc/{pid}/maps",
        device=serial
    )
    
    # Cari region heap/anonymous
    session_region = None
    for line in maps.split("\n"):
        if "heap" in line or "[anon" in line:
            parts = line.split()
            if parts:
                addr_range = parts[0]
                start, end = addr_range.split("-")
                size = int(end, 16) - int(start, 16)
                if size < 50 * 1024 * 1024:  # skip region > 50MB
                    session_region = (int(start, 16), int(end, 16))
                    break
    
    if not session_region:
        print(f"  {Y}  Tidak bisa baca memory maps{RESET}")
        return None
    
    print(f"  Mencari session pattern di memory...")
    
    # Dump dan cari pattern
    start_hex = hex(session_region[0])[2:]
    size = session_region[1] - session_region[0]
    
    code, out, _ = run_adb(
        "shell", "su", "-c",
        f"dd if=/proc/{pid}/mem bs=1 skip=$(( 0x{start_hex} )) count={min(size, 1024*1024)} 2>/dev/null | strings",
        device=serial
    )
    
    if out:
        # Cari session pattern: 32 hex chars
        sessions = re.findall(r'[0-9a-f]{32,64}', out)
        uuids = re.findall(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            out
        )
        
        if sessions or uuids:
            print(f"  {G}✅ Ditemukan kandidat session dari memory!{RESET}")
            for s in sessions[:3]:
                print(f"    hex: {s}")
            for u in uuids[:3]:
                print(f"    uuid: {u}")
    
    return None


def save_session(data: dict):
    """Simpan session ke file dan tampilkan instruksi."""
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    user_id = data.get("user_id", "")
    session = data.get("session", "")
    source  = data.get("source", "?")
    
    print(f"""
{G}{BOLD}╔══════════════════════════════════════════════════════════╗
║                ✅ SESSION BERHASIL CAPTURED!             ║
╚══════════════════════════════════════════════════════════╝{RESET}

  {Y}user-id :{RESET} {user_id}
  {Y}session :{RESET} {session[:20]}{'...' if len(session) > 20 else ''}
  {DIM}source  : {source}{RESET}

{BOLD}📋 Kirim ke bot Telegram:{RESET}
  /session set {user_id} {session}

{BOLD}💾 Disimpan ke:{RESET} {OUTPUT_FILE}
""")


def interactive_mode():
    """Mode interaktif — pilih device dan metode."""
    banner()
    
    # 1. Cek ADB
    if not check_adb():
        return
    
    # 2. Deteksi device
    print(f"\n{DIM}🔍 Mencari device yang terhubung...{RESET}")
    devices = get_devices()
    
    serial = None
    if not devices:
        print(f"{Y}⚠️  Tidak ada device terhubung.{RESET}")
        choice = input(f"\nTunggu HP terhubung? [y/n]: ").strip().lower()
        if choice == "y":
            serial = wait_for_device()
        if not serial:
            print(f"\n{BOLD}📋 Panduan aktivasi USB Debugging:{RESET}")
            print(f"""
  {Y}1.{RESET} Settings → About Phone
  {Y}2.{RESET} Tap "Build Number" 7x sampai muncul "You are a developer!"
  {Y}3.{RESET} Settings → Developer Options → USB Debugging ✓
  {Y}4.{RESET} Colok HP ke laptop, tap Allow di popup
  {Y}5.{RESET} Jalankan script ini lagi
""")
            return
    else:
        if len(devices) == 1:
            serial = devices[0]["serial"]
            print(f"{G}✅ Device: {serial} {devices[0]['details']}{RESET}")
        else:
            print(f"\n{BOLD}Pilih device:{RESET}")
            for i, d in enumerate(devices):
                print(f"  {Y}{i+1}{RESET} → {d['serial']} {d['details']}")
            idx = int(input("Nomor device: ").strip()) - 1
            serial = devices[idx]["serial"]
    
    # 3. Cari Sky
    sky_pkg = find_sky_package(serial)
    if not sky_pkg:
        return
    
    # 4. Grab session
    print(f"\n{BOLD}Metode grab session yang akan dicoba:{RESET}")
    print(f"  {Y}1{RESET} SharedPreferences (data/data/<pkg>/shared_prefs/)")
    print(f"  {Y}2{RESET} SQLite database")
    print(f"  {Y}3{RESET} App files (JSON)")
    print(f"  {Y}4{RESET} Logcat monitor (buka Sky → login saat monitoring)")
    print(f"  {Y}5{RESET} Memory dump (butuh root)\n")
    
    result = grab_session_methods(serial, sky_pkg)
    
    if result:
        save_session(result)
    else:
        print(f"""
{Y}⚠️  Session tidak ter-capture secara otomatis.{RESET}

{BOLD}Alternatif — Intercept via Proxy:{RESET}

  {Y}1.{RESET} Install HTTP Toolkit di laptop: {BOLD}httptoolkit.com{RESET}
  {Y}2.{RESET} Buka HTTP Toolkit → "Android Device via ADB"
  {Y}3.{RESET} Klik "Setup Device" → otomatis setup proxy + certificate
  {Y}4.{RESET} Buka Sky → login
  {Y}5.{RESET} Di HTTP Toolkit, filter {BOLD}live.radiance.thatgamecompany.com{RESET}
  {Y}6.{RESET} Copy header {BOLD}session{RESET} dan {BOLD}user-id{RESET}
  {Y}7.{RESET} Kirim ke bot: {BOLD}/session set <user-id> <session>{RESET}

{BOLD}Atau pakai mitmproxy:{RESET}
  python session_grabber.py --mode 1
""")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Sky CoTL ADB Session Grabber"
    )
    parser.add_argument("--serial", "-s", help="Serial device ADB spesifik")
    parser.add_argument("--package", "-p",
                        default="com.tgc.sky.android",
                        help="Package name Sky")
    parser.add_argument("--method", "-m",
                        choices=["prefs", "sqlite", "files", "logcat", "memory", "all"],
                        default="all",
                        help="Metode grab yang dipakai")
    args = parser.parse_args()
    
    if args.serial:
        # Non-interactive mode
        if not check_adb():
            sys.exit(1)
        
        result = None
        pkg = args.package
        
        if args.method in ["prefs", "all"]:
            result = _method_shared_prefs(args.serial, pkg)
        if not result and args.method in ["sqlite", "all"]:
            result = _method_sqlite(args.serial, pkg)
        if not result and args.method in ["files", "all"]:
            result = _method_app_files(args.serial, pkg)
        if not result and args.method in ["logcat", "all"]:
            result = _method_logcat(args.serial, pkg)
        if not result and args.method in ["memory", "all"]:
            result = _method_memory(args.serial, pkg)
        
        if result:
            save_session(result)
            sys.exit(0)
        else:
            print(f"{R}Session tidak ter-capture{RESET}")
            sys.exit(1)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
