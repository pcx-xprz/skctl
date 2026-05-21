#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║       Sky CoTL — ADB Session Grabber                        ║
║       Grab session via USB Debug ATAU WiFi (tanpa kabel)    ║
╠══════════════════════════════════════════════════════════════╣
║  CARA PAKAI (USB):                                          ║
║  1. Aktifkan USB Debugging di HP                            ║
║  2. Colok HP ke laptop via USB                              ║
║  3. Jalankan: python adb_session_grabber.py                 ║
║                                                              ║
║  CARA PAKAI (WiFi - tanpa kabel):                           ║
║  1. HP dan laptop di WiFi yang sama                         ║
║  2. python adb_session_grabber.py --wifi <IP_HP>            ║
║     atau jalankan interaktif → pilih mode WiFi              ║
╚══════════════════════════════════════════════════════════════╝

Requirements:
  pip install requests
  
ADB:
  Windows: https://developer.android.com/tools/releases/platform-tools
  Mac:     brew install android-platform-tools
  Linux:   sudo apt install adb

TROUBLESHOOT (adb devices kosong):
  1. USB Debugging belum aktif
     → Settings > About Phone > tap Build Number 7x
     → Settings > Developer Options > USB Debugging ✓
  2. Mode USB salah
     → Notif HP setelah colok USB → pilih "File Transfer" bukan "Charge"
  3. Driver ADB Windows belum install
     → Install Universal ADB Driver: https://adb.clockworkmod.com/
     → Atau jalankan: fix_adb_windows.bat
"""

import json
import os
import re
import socket
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

OUTPUT_FILE  = "sky_session_result.json"
ADB_WIFI_PORT = 5555


def banner():
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════╗
║     🔌  Sky CoTL ADB Session Grabber  📶               ║
║     USB Debug  /  WiFi (tanpa kabel)  /  Logcat        ║
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


def diagnose_adb_empty():
    """Tampilkan panduan fix ketika adb devices kosong."""
    print(f"""
{Y}{BOLD}⚠️  adb devices kosong — 3 kemungkinan penyebab:{RESET}

{BOLD}PENYEBAB 1 — USB Debugging belum aktif (paling umum){RESET}
  Di HP kamu:
  {Y}1.{RESET} Settings → About Phone
  {Y}2.{RESET} Tap {BOLD}"Build Number"{RESET} sebanyak {BOLD}7 kali{RESET} berturut-turut
     (muncul notif "You are a developer!")
  {Y}3.{RESET} Settings → Developer Options
  {Y}4.{RESET} Aktifkan {BOLD}"USB Debugging"{RESET} ✓
  {Y}5.{RESET} Cabut dan colok ulang kabel USB
  {Y}6.{RESET} Tap {BOLD}"Allow"{RESET} di popup HP

{BOLD}PENYEBAB 2 — Mode USB salah (Charge Only){RESET}
  Setelah colok USB, lihat notifikasi di HP:
  {Y}→{RESET} Tap notif → pilih {BOLD}"File Transfer (MTP)"{RESET}
  {Y}→{RESET} BUKAN "Charge Only"

{BOLD}PENYEBAB 3 — Driver ADB Windows belum install{RESET}
  {Y}→{RESET} Buka Device Manager (Win+X → Device Manager)
  {Y}→{RESET} Cari device dengan tanda ! kuning
  {Y}→{RESET} Klik kanan → Update Driver
  
  Atau install Universal ADB Driver:
  {BOLD}https://adb.clockworkmod.com/{RESET}

{BOLD}FIX CEPAT:{RESET}
  Jalankan: {BOLD}fix_adb_windows.bat{RESET}  (ada di folder tools/)

{DIM}──────────────────────────────────────────────{RESET}
{BOLD}Alternatif: ADB via WiFi (tanpa kabel){RESET}
  Tidak perlu USB sama sekali!
  Syarat: HP dan laptop di WiFi yang sama
  Cara: python adb_session_grabber.py --wifi <IP_HP>
""")


def setup_adb_wifi(hp_ip: str, serial_usb: str = None) -> Optional[str]:
    """
    Setup ADB over WiFi.
    
    Jika serial_usb diberikan: aktifkan mode TCP via USB dulu lalu disconnect.
    Jika tidak: langsung coba connect ke IP (Android 11+ support wireless debug).
    
    Returns serial WiFi "IP:PORT" atau None.
    """
    print(f"\n{BOLD}📶 Setup ADB via WiFi ke {hp_ip}...{RESET}")

    # Android 11+ support wireless debugging langsung (port 5037 default)
    # Android 10 kebawah butuh USB dulu untuk aktifkan TCP mode

    if serial_usb:
        # Aktifkan TCP/IP mode via USB
        print(f"  {DIM}Mengaktifkan TCP mode via USB...{RESET}")
        run_adb("tcpip", ADB_WIFI_PORT, device=serial_usb)
        time.sleep(2)
        print(f"  {G}✅ TCP mode aktif di port {ADB_WIFI_PORT}{RESET}")
        print(f"  {Y}Sekarang bisa cabut kabel USB{RESET}")
        time.sleep(1)

    # Connect via WiFi
    target = f"{hp_ip}:{ADB_WIFI_PORT}"
    print(f"  Connecting ke {target}...")
    code, out, err = run_adb("connect", target)

    if "connected" in out.lower():
        print(f"  {G}✅ Terhubung via WiFi: {target}{RESET}")
        # Verifikasi device muncul
        time.sleep(2)
        devices = get_devices()
        wifi_dev = next((d for d in devices if hp_ip in d["serial"]), None)
        if wifi_dev:
            return wifi_dev["serial"]

    # Coba port lain (Android 11+ pakai port random)
    print(f"  {Y}Port {ADB_WIFI_PORT} gagal, coba scan port wireless debug...{RESET}")
    for port in [5555, 5037, 5554, 37000, 38000, 39000, 40000]:
        target = f"{hp_ip}:{port}"
        code, out, _ = run_adb("connect", target)
        if "connected" in out.lower() and "refused" not in out.lower():
            print(f"  {G}✅ Connected via port {port}!{RESET}")
            return target

    print(f"""
  {R}❌ Gagal connect via WiFi{RESET}
  
  {BOLD}Cara aktifkan Wireless Debugging di HP:{RESET}
  
  {Y}Android 11+:{RESET}
    Settings → Developer Options → Wireless Debugging
    Aktifkan → tap "Pair device with QR code" atau "Pair device with pairing code"
    
  {Y}Android 10 ke bawah:{RESET}
    Butuh USB dulu untuk aktifkan TCP mode:
    1. Colok USB
    2. Jalankan script lagi dengan --wifi {hp_ip}
    3. Setelah setup, bisa cabut USB
""")
    return None


def scan_local_network_for_android() -> list[str]:
    """Scan jaringan lokal untuk mencari device Android dengan ADB port terbuka."""
    print(f"\n{DIM}🔍 Scan jaringan lokal untuk Android...{RESET}")

    # Ambil IP laptop
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        print(f"  {Y}Tidak bisa detect IP lokal{RESET}")
        return []

    # Ambil subnet
    parts = local_ip.split(".")
    subnet = ".".join(parts[:3])
    print(f"  IP laptop: {local_ip}")
    print(f"  Scan subnet: {subnet}.1 - {subnet}.254 port 5555...")

    found = []
    import concurrent.futures

    def check_port(ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, 5555))
            sock.close()
            if result == 0:
                return ip
        except Exception:
            pass
        return None

    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        results = list(ex.map(check_port, ips))

    found = [r for r in results if r]
    if found:
        print(f"  {G}✅ Ditemukan {len(found)} device dengan port 5555 terbuka: {found}{RESET}")
    else:
        print(f"  Tidak ada device ADB WiFi ditemukan di subnet ini")

    return found


def get_devices() -> list[dict]:
    """Ambil daftar device yang terhubung (USB + WiFi)."""
    code, out, err = run_adb("devices", "-l")
    devices = []

    for line in out.split("\n")[1:]:  # Skip header
        line = line.strip()
        if not line or "offline" in line or "unauthorized" in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            info = {
                "serial":  parts[0],
                "details": " ".join(parts[2:]),
                "type":    "wifi" if ":" in parts[0] else "usb",
            }
            devices.append(info)

    return devices


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
    """Monitor logcat ALL — tangkap semua output termasuk native library."""

    print(f"""
  {BOLD}📋 Logcat Monitor (ALL tags){RESET}

  {Y}Langkah:{RESET}
  1. Script monitor SEMUA logcat HP
  2. {BOLD}Buka Sky di HP{RESET}
  3. {BOLD}Tap tombol Login → pilih Facebook → selesai login{RESET}
  4. Session otomatis ter-capture!

  {DIM}(Tekan Ctrl+C untuk skip){RESET}
""")

    input("  Tekan ENTER untuk mulai...")

    print(f"\n  {G}▶ Monitoring... Buka Sky sekarang dan login!{RESET}")
    print(f"  {DIM}(Ctrl+C untuk stop){RESET}\n")

    run_adb("logcat", "-c", device=serial)

    # Pattern session Sky — lebih agresif
    patterns = [
        # Session hex 32 chars setelah keyword
        (r'(?:session|Session)["\s:=]+([0-9a-f]{32,64})',         "session"),
        # UUID setelah user-id keyword
        (r'(?:user.?id|userId|user_id)["\s:=]+"?'
         r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', "user_id"),
        # JSON field "session":"xxx"
        (r'"session"\s*:\s*"([0-9a-f]{16,64})"',                  "session"),
        # JSON field "user_id"/"user-id"
        (r'"user.?id"\s*:\s*"([0-9a-f-]{8,})"',                   "user_id"),
        # HTTP header format  session: xxxx
        (r'\bsession\b[:\s]+([0-9a-f]{16,})',                      "session"),
        # Standalone 32-char hex (bisa session)
        (r'\b([0-9a-f]{32})\b',                                    "hex32"),
        # UUID standalone
        (r'\b([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
         r'[89ab][0-9a-f]{3}-[0-9a-f]{12})\b',                    "uuid"),
    ]

    session = None
    user_id = None
    hex32_candidates: list[str] = []

    try:
        # Gunakan *:V untuk ALL verbose — tangkap output native library juga
        proc = subprocess.Popen(
            ["adb", "-s", serial, "logcat", "-v", "brief", "*:V"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )

        start   = time.time()
        timeout = 180  # 3 menit

        while time.time() - start < timeout:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.01)
                continue

            # Print baris yang mengandung keyword penting
            lower = line.lower()
            if any(kw in lower for kw in
                   ["session", "user_id", "userid", "user-id",
                    "login", "auth", "account", "radiance", "tgc"]):
                print(f"  {DIM}{line.rstrip()[:120]}{RESET}")

            # Cari pattern
            for pat, kind in patterns:
                for m in re.finditer(pat, line, re.IGNORECASE):
                    val = m.group(1)
                    if kind == "session" and not session and len(val) >= 16:
                        session = val
                        print(f"\n  {G}✅ session  : {val[:20]}...{RESET}")
                    elif kind == "user_id" and not user_id:
                        user_id = val
                        print(f"\n  {G}✅ user_id  : {val}{RESET}")
                    elif kind == "uuid" and not user_id:
                        user_id = val
                        print(f"\n  {G}✅ uuid     : {val}{RESET}")
                    elif kind == "hex32" and val not in hex32_candidates:
                        hex32_candidates.append(val)

            if session and user_id:
                proc.terminate()
                return {"user_id": user_id, "session": session, "source": "logcat_all"}

        proc.terminate()

    except KeyboardInterrupt:
        print(f"\n  {Y}Dihentikan{RESET}")

    # Tampilkan kandidat hex32 jika belum dapat session
    if hex32_candidates:
        print(f"\n  {Y}Kandidat hex32 yang ditemukan (mungkin salah satunya session):{RESET}")
        for h in hex32_candidates[-10:]:
            print(f"    {h}")
        if not session and len(hex32_candidates) >= 1:
            print(f"\n  {Y}Coba set manual dengan hex32 terakhir:{RESET}")
            print(f"  /session set <user_id> {hex32_candidates[-1]}")

    if not session:
        print(f"\n  {DIM}Session tidak ter-capture via logcat.{RESET}")
        print(f"  {Y}Sky native binary mungkin tidak log session ke logcat.{RESET}")

    return None


def _method_tcpdump(serial: str, package: str) -> Optional[dict]:
    """
    Intercept traffic langsung di HP pakai tcpdump (jika tersedia).
    Tangkap header HTTP yang mengandung session.
    """
    print(f"\n{C}[TCPDUMP]{RESET} Cek tcpdump di HP...")

    # Cek apakah tcpdump tersedia
    code, out, _ = run_adb("shell", "which tcpdump", device=serial)
    if code != 0 or not out:
        code, out, _ = run_adb("shell", "ls /system/bin/tcpdump", device=serial)
        if code != 0:
            print(f"  {DIM}→ tcpdump tidak ada di HP ini{RESET}")
            return None

    print(f"  {G}✅ tcpdump tersedia!{RESET}")
    print(f"""
  {BOLD}Langkah:{RESET}
  1. Script akan jalankan tcpdump di HP
  2. {BOLD}Buka Sky → login{RESET}
  3. Header session akan ter-capture dari traffic

  {DIM}(Ctrl+C untuk stop){RESET}
""")
    input("  Tekan ENTER untuk mulai...")

    session = None
    user_id = None

    try:
        # Jalankan tcpdump + pipe ke strings untuk lihat ASCII
        proc = subprocess.Popen(
            ["adb", "-s", serial, "shell",
             "tcpdump -i any -A -s 0 'host live.radiance.thatgamecompany.com' 2>/dev/null"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )

        start = time.time()
        buffer = ""

        while time.time() - start < 120:
            chunk = proc.stdout.read(512)
            if not chunk:
                time.sleep(0.05)
                continue

            buffer += chunk
            lines  = buffer.split("\n")
            buffer = lines[-1]

            for line in lines[:-1]:
                # Cari session header
                sm = re.search(r'session:\s*([0-9a-f]{16,64})', line, re.IGNORECASE)
                um = re.search(
                    r'user.?id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
                    r'-[0-9a-f]{4}-[0-9a-f]{12})',
                    line, re.IGNORECASE
                )
                if sm:
                    session = sm.group(1)
                    print(f"\n  {G}✅ SESSION: {session[:20]}...{RESET}")
                if um:
                    user_id = um.group(1)
                    print(f"\n  {G}✅ USER-ID: {user_id}{RESET}")

                if session and user_id:
                    proc.terminate()
                    return {
                        "user_id": user_id,
                        "session": session,
                        "source":  "tcpdump",
                    }

        proc.terminate()
    except KeyboardInterrupt:
        print(f"\n  {Y}Dihentikan{RESET}")

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

    # 2. Restart server dulu (fix common issues)
    print(f"\n{DIM}🔄 Restart ADB server...{RESET}")
    run_adb("kill-server")
    time.sleep(1)
    run_adb("start-server")

    # 3. Deteksi device
    print(f"\n{DIM}🔍 Mencari device...{RESET}")
    devices = get_devices()

    serial = None

    if not devices:
        # Cek unauthorized / offline
        code, raw_out, _ = run_adb("devices")
        if "unauthorized" in raw_out:
            print(f"\n{Y}⚠️  HP terdeteksi tapi UNAUTHORIZED!{RESET}")
            print(f"   → Lihat HP kamu → ada popup {BOLD}'Allow USB Debugging?'{RESET}")
            print(f"   → Tap {BOLD}ALLOW{RESET} / {BOLD}OK{RESET}")
            print(f"\n   Menunggu 15 detik...")
            for i in range(15, 0, -1):
                print(f"\r   {i}...", end="", flush=True)
                time.sleep(1)
            print()
            devices = get_devices()

        if not devices:
            diagnose_adb_empty()
            print(f"\n{BOLD}Pilih tindakan:{RESET}")
            print(f"  {Y}1{RESET} → Coba lagi (sudah fix USB Debugging)")
            print(f"  {Y}2{RESET} → Setup ADB via WiFi (tanpa kabel)")
            print(f"  {Y}3{RESET} → Scan jaringan lokal untuk Android")
            print(f"  {Y}0{RESET} → Keluar")

            choice = input(f"\n{BOLD}Pilihan: {RESET}").strip()

            if choice == "1":
                devices = get_devices()
                if not devices:
                    print(f"{R}Masih kosong. Coba fix dulu lalu jalankan script lagi.{RESET}")
                    return

            elif choice == "2":
                hp_ip = input(
                    f"\nMasukkan IP HP kamu\n"
                    f"{DIM}(cek di Settings → WiFi → tap nama WiFi → IP Address){RESET}\n"
                    f"IP: "
                ).strip()
                if not hp_ip:
                    return
                serial = setup_adb_wifi(hp_ip)
                if not serial:
                    return

            elif choice == "3":
                found_ips = scan_local_network_for_android()
                if not found_ips:
                    print(f"{R}Tidak ada Android ditemukan.{RESET}")
                    return
                if len(found_ips) == 1:
                    hp_ip = found_ips[0]
                else:
                    print(f"\n{BOLD}Pilih IP:{RESET}")
                    for i, ip in enumerate(found_ips, 1):
                        print(f"  {Y}{i}{RESET} → {ip}")
                    idx = int(input("Nomor: ").strip()) - 1
                    hp_ip = found_ips[idx]
                serial = setup_adb_wifi(hp_ip)
                if not serial:
                    return
            else:
                return

    # 4. Pilih device jika lebih dari 1
    if not serial:
        if len(devices) == 1:
            serial = devices[0]["serial"]
            dtype  = devices[0]["type"]
            icon   = "📶" if dtype == "wifi" else "🔌"
            print(f"{G}✅ Device: {icon} {serial} {devices[0]['details']}{RESET}")
        else:
            print(f"\n{BOLD}Pilih device:{RESET}")
            for i, d in enumerate(devices, 1):
                icon = "📶" if d["type"] == "wifi" else "🔌"
                print(f"  {Y}{i}{RESET} → {icon} {d['serial']} {d['details']}")
            try:
                idx    = int(input("Nomor device: ").strip()) - 1
                serial = devices[idx]["serial"]
            except (ValueError, IndexError):
                print(f"{R}Pilihan tidak valid{RESET}")
                return

    # ── Jika punya USB, tawarkan setup WiFi sekarang ──────────────────────────
    if ":" not in serial:  # USB device
        print(f"\n{DIM}💡 Tip: Mau setup WiFi mode sekarang biar bisa cabut kabel? (opsional){RESET}")
        wifi_now = input("Setup WiFi ADB? [y/n]: ").strip().lower()
        if wifi_now == "y":
            # Ambil IP HP otomatis
            code, ip_out, _ = run_adb("shell", "ip", "route", device=serial)
            ip_match = re.search(r"src\s+([\d.]+)", ip_out)
            if ip_match:
                hp_ip  = ip_match.group(1)
                print(f"  {G}IP HP: {hp_ip}{RESET}")
            else:
                hp_ip = input("  Masukkan IP HP manual: ").strip()

            wifi_serial = setup_adb_wifi(hp_ip, serial_usb=serial)
            if wifi_serial:
                print(f"  {G}✅ Sekarang bisa cabut kabel! WiFi ADB aktif.{RESET}")
                use_wifi = input("  Ganti ke WiFi mode? [y/n]: ").strip().lower()
                if use_wifi == "y":
                    serial = wifi_serial

    # 5. Cari Sky
    sky_pkg = find_sky_package(serial)
    if not sky_pkg:
        return

    # 6. Grab session
    print(f"\n{BOLD}Metode grab session:{RESET}")
    print(f"  {Y}1{RESET} SharedPreferences  {DIM}(data/data/<pkg>){RESET}")
    print(f"  {Y}2{RESET} SQLite database")
    print(f"  {Y}3{RESET} App files (JSON)")
    print(f"  {Y}4{RESET} {BOLD}Logcat Monitor{RESET}     {DIM}← Paling efektif! Buka Sky & login{RESET}")
    print(f"  {Y}5{RESET} Memory dump        {DIM}(butuh root){RESET}")
    print(f"  {Y}A{RESET} Coba semua otomatis\n")

    method_choice = input(f"{BOLD}Pilihan [1-5/A]: {RESET}").strip().upper()

    result = None
    if method_choice == "1":
        result = _method_shared_prefs(serial, sky_pkg)
    elif method_choice == "2":
        result = _method_sqlite(serial, sky_pkg)
    elif method_choice == "3":
        result = _method_app_files(serial, sky_pkg)
    elif method_choice == "4":
        result = _method_logcat(serial, sky_pkg)
    elif method_choice == "5":
        result = _method_memory(serial, sky_pkg)
    else:
        result = grab_session_methods(serial, sky_pkg)

    if result:
        save_session(result)
    else:
        print(f"""
{Y}⚠️  Session tidak ter-capture otomatis.{RESET}

{BOLD}Rekomendasi selanjutnya:{RESET}

  {Y}A.{RESET} HTTP Toolkit (paling mudah):
     • Download: {BOLD}httptoolkit.com{RESET}
     • Buka → "Android Device via ADB"
     • Klik Setup → buka Sky → login
     • Copy header {BOLD}session{RESET} dan {BOLD}user-id{RESET}

  {Y}B.{RESET} Coba logcat lagi (metode 4):
     • Pastikan Sky sudah terbuka di HP
     • Lakukan login ulang saat monitoring jalan

  {Y}C.{RESET} Kirim ke bot setelah dapat:
     {BOLD}/session set <user-id> <session>{RESET}
""")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Sky CoTL ADB Session Grabber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python adb_session_grabber.py                     interaktif
  python adb_session_grabber.py --wifi 192.168.1.5  WiFi tanpa kabel
  python adb_session_grabber.py --serial R9JT204XXXX logcat saja
  python adb_session_grabber.py --method logcat      logcat saja
  python adb_session_grabber.py --scan               scan jaringan
        """
    )
    parser.add_argument("--serial",  "-s", help="Serial device ADB spesifik")
    parser.add_argument("--wifi",    "-w", metavar="IP",
                        help="Langsung setup + gunakan ADB via WiFi ke IP HP")
    parser.add_argument("--scan",    action="store_true",
                        help="Scan jaringan lokal untuk Android dengan ADB port terbuka")
    parser.add_argument("--package", "-p",
                        default="com.tgc.sky.android",
                        help="Package name Sky (default: com.tgc.sky.android)")
    parser.add_argument("--method",  "-m",
                        choices=["prefs", "sqlite", "files", "logcat", "memory", "all"],
                        default="all",
                        help="Metode grab yang dipakai (default: all)")
    args = parser.parse_args()

    if not check_adb():
        sys.exit(1)

    # ── Mode scan jaringan ────────────────────────────────────────────────────
    if args.scan:
        banner()
        found = scan_local_network_for_android()
        if found:
            print(f"\n{BOLD}Connect ke salah satu? [y/n]:{RESET} ", end="")
            if input().strip().lower() == "y":
                hp_ip = found[0] if len(found) == 1 else \
                    found[int(input("Nomor IP: ").strip()) - 1]
                serial = setup_adb_wifi(hp_ip)
                if serial:
                    pkg = find_sky_package(serial)
                    if pkg:
                        result = grab_session_methods(serial, pkg)
                        if result:
                            save_session(result)
        return

    # ── Mode WiFi langsung ────────────────────────────────────────────────────
    if args.wifi:
        banner()
        # Cek apakah ada USB device untuk aktifkan TCP dulu
        devices    = get_devices()
        usb_serial = next((d["serial"] for d in devices if ":" not in d["serial"]), None)
        serial     = setup_adb_wifi(args.wifi, serial_usb=usb_serial)
        if not serial:
            sys.exit(1)
        pkg = args.package
        if not find_sky_package(serial):
            sys.exit(1)
        result = None
        if args.method in ["prefs",   "all"]: result = _method_shared_prefs(serial, pkg)
        if not result and args.method in ["sqlite",  "all"]: result = _method_sqlite(serial, pkg)
        if not result and args.method in ["files",   "all"]: result = _method_app_files(serial, pkg)
        if not result and args.method in ["logcat",  "all"]: result = _method_logcat(serial, pkg)
        if not result and args.method in ["memory",  "all"]: result = _method_memory(serial, pkg)
        if result:
            save_session(result)
            sys.exit(0)
        sys.exit(1)

    # ── Mode serial spesifik ──────────────────────────────────────────────────
    if args.serial:
        pkg    = args.package
        serial = args.serial
        result = None
        if args.method in ["prefs",   "all"]: result = _method_shared_prefs(serial, pkg)
        if not result and args.method in ["sqlite",  "all"]: result = _method_sqlite(serial, pkg)
        if not result and args.method in ["files",   "all"]: result = _method_app_files(serial, pkg)
        if not result and args.method in ["logcat",  "all"]: result = _method_logcat(serial, pkg)
        if not result and args.method in ["memory",  "all"]: result = _method_memory(serial, pkg)
        if result:
            save_session(result)
            sys.exit(0)
        sys.exit(1)

    # ── Mode interaktif (default) ─────────────────────────────────────────────
    interactive_mode()


if __name__ == "__main__":
    main()
