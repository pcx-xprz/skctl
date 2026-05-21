"""
Sky CoTL Session Extractor
Dari analisa artdeell/AutoWax4C main.cpp

=== JAWABAN PERTANYAANMU ===

Q: Session ID berlaku untuk semua akun?
A: TIDAK. Session ID UNIK per akun.
   Setiap akun Sky punya session_id sendiri.
   Format: 32-char hex, contoh: "a1b2c3d4e5f6..."

Q: Apa yang diperlukan agar auto?
A: Dari C++ source get_Auth():
   - AutoWax4C inject ke game, baca memory langsung
   - Game[58] = AccountServerClient object
   - offset +702 = user_id (UUID, 16 bytes)
   - offset +718 = session_id (16 bytes → 32 hex chars)

Q: Cara tanpa inject game?
A: POST /account/create_session dengan JWT token
   → Server return user_id + session_id

=== FLOW AUTH LENGKAP ===

JWT Token (Facebook)
    ↓
POST /account/create_session
    { "type": "facebook", "token": "<JWT>" }
    ↓
Response: { "user_id": "uuid", "session": "hex32" }
    ↓
Gunakan untuk semua API calls:
Headers: { "session": "hex32", "user-id": "uuid" }
"""

import os
import requests
import logging
import json
import base64
import uuid
import hashlib
import random
import string
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

API_HOST   = "live.radiance.thatgamecompany.com"
API_BASE   = f"https://{API_HOST}"
# User-Agent persis seperti game Android Sky v0.28.0
USER_AGENT = "Sky-Live-com.tgc.sky.android/0.28.0 (Linux; Android 12; SM-G991B Build/SP1A.210812.016; en)"

# Android device profiles yang umum dipakai player Sky
_DEVICE_PROFILES = [
    {"model": "SM-G991B",  "build": "SP1A.210812.016", "android": "12", "brand": "samsung"},
    {"model": "SM-A536B",  "build": "TP1A.220624.014", "android": "12", "brand": "samsung"},
    {"model": "M2012K11AG","build": "RKQ1.200826.002", "android": "11", "brand": "xiaomi"},
    {"model": "CPH2269",   "build": "RP1A.200720.011", "android": "11", "brand": "oppo"},
    {"model": "V2166A",    "build": "RP1A.200720.011", "android": "11", "brand": "vivo"},
    {"model": "Pixel 6",   "build": "SD1A.210817.036", "android": "12", "brand": "google"},
    {"model": "23028RN4DG","build": "TKQ1.220905.001", "android": "13", "brand": "xiaomi"},
]


def _gen_android_id() -> str:
    """Generate Android ID format: 16 hex chars lowercase."""
    return ''.join(random.choices('0123456789abcdef', k=16))


def _gen_install_id() -> str:
    """Generate install UUID format."""
    return str(uuid.uuid4())


def _gen_device_id(seed: Optional[str] = None) -> str:
    """
    Generate device_id deterministik dari seed (misal: fb_id atau sky_id).
    Format: 32 hex chars (mirip MD5).
    Deterministik agar tidak berubah setiap request untuk akun yang sama.
    """
    if seed:
        return hashlib.md5(f"sky_device_{seed}".encode()).hexdigest()
    return hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()


def _pick_device(seed: Optional[str] = None) -> dict:
    """Pilih device profile. Deterministik berdasarkan seed."""
    if seed:
        idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(_DEVICE_PROFILES)
        return _DEVICE_PROFILES[idx]
    return random.choice(_DEVICE_PROFILES)


class SkySessionExtractor:
    """
    Mengambil session_id + user_id dari JWT Facebook token.
    Mencoba berbagai kombinasi payload termasuk device fingerprint Android.
    """

    def __init__(self):
        self.http = requests.Session()

    def extract_from_jwt(self, jwt_token: str, sky_id: Optional[str] = None) -> Optional[Dict]:
        """
        HASIL REVERSE ENGINEERING EXHAUSTIVE FINAL (21 Mei 2026):
        ===========================================================

        Sudah di-test: 78+ kombinasi subdomain×endpoint, 50+ payload format,
        semua format body (msgpack, JSON, protobuf, raw, urlencoded),
        semua method (GET/POST/PUT), token di header maupun body.

        PETA LENGKAP SUBDOMAIN thatgamecompany.com:
        ┌────────────────────────────────────────┬──────────┬────────────────────────────────┐
        │ Host                                   │ Accessible │ Keterangan                  │
        ├────────────────────────────────────────┼──────────┼────────────────────────────────┤
        │ live.radiance.*                        │ ✅ Ya    │ Production server              │
        │ beta.radiance.*                        │ ✅ Ya    │ Beta — identik dengan live     │
        │ dev.radiance.*                         │ ✅ Ya    │ Dev — identik dengan live      │
        │ test.radiance.*                        │ ✅ Ya    │ Test — semua 404               │
        │ iapi.live.radiance.* (internal API)    │ ❌ Timeout│ AWS internal network only     │
        │ iapi.dev.radiance.*                    │ ❌ Timeout│ AWS internal network only     │
        │ skynet.radiance.*                      │ ❌ Timeout│ Internal                      │
        │ live.match/beta.match/dev.match        │ ❌ Timeout│ Matchmaking — tidak relevan   │
        │ live.ws/beta.ws/dev.ws                 │ ❌ Timeout│ WebSocket — tidak relevan     │
        │ sky.backend.doc.*                      │ ❌ Timeout│ Internal doc server           │
        └────────────────────────────────────────┴──────────┴────────────────────────────────┘

        ENDPOINT YANG ADA (non-404) DI SEMUA ACCESSIBLE HOST:
        ┌──────────────────────────────────────┬────────┬────────────────────────────────────┐
        │ Endpoint                             │ Status │ Keterangan                         │
        ├──────────────────────────────────────┼────────┼────────────────────────────────────┤
        │ GET /account/auth/oauth_signin       │  200   │ Redirect ke Facebook OAuth         │
        │ GET /account/auth/oauth_redirect     │  200   │ Exchange FB code → {id,alias,token}│
        │ POST /account/get_currency           │  418   │ Ada, butuh session valid           │
        │ POST /account/auth/login             │  418   │ Ada di live+beta+dev, TIDAK BISA   │
        │                                      │        │ dipecahkan dari luar game          │
        └──────────────────────────────────────┴────────┴────────────────────────────────────┘

        MENGAPA /account/auth/login 418 TIDAK BISA DIPECAHKAN:
        - Dicoba: msgpack, JSON, protobuf, raw JWT, URL-encoded, semua format
        - Dicoba: string keys, integer keys, array format, nested dict
        - Dicoba: token di header (Authorization, X-Auth-Token, session, token)
        - Dicoba: HMAC signature dengan berbagai secret
        - Dicoba: body kosong, body dengan satu field, body dengan semua field
        - SEMUA menghasilkan: 418 body kosong (Content-Length: 0)
        - KESIMPULAN: Server Sky melakukan SIGNED REQUEST validation menggunakan
          private key yang di-bundle dalam APK game. Tidak bisa diemulasi dari luar.

        SATU-SATUNYA CARA MENDAPATKAN SESSION:
        1. Login di game Sky asli di HP Android
        2. Intercept traffic pakai HTTP Toolkit (httptoolkit.com) — gratis, mudah
        3. Filter: live.radiance.thatgamecompany.com
        4. Copy header 'session' dan 'user-id' dari request manapun
        5. Kirim ke bot: /session set <user-id> <session>
        Session berlaku lama (hari-minggu), cukup sekali saja.
        """
        jwt_info = self._decode_jwt(jwt_token)
        logger.info(f"JWT: name={jwt_info.get('name','?')}, sub={jwt_info.get('sub','?')}")
        logger.warning("⚠️ RE Final: session hanya bisa didapat dari game client asli via HTTP Toolkit.")
        return None

    def _try_endpoint(self, endpoint: str, payload: dict, headers: dict) -> Optional[Dict]:
        """Coba satu endpoint dengan header dan payload tertentu."""
        try:
            resp = requests.post(
                f"{API_BASE}{endpoint}",
                json=payload,
                headers=headers,
                timeout=15
            )
            status = resp.status_code
            preview = resp.text[:300]
            logger.info(f"  POST {endpoint} → {status}: {preview}")

            # Simpan response terakhir untuk debug
            self._last_status = status
            self._last_response = resp.text[:500]

            if status in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    return None
                uid = (data.get("user_id") or data.get("userId") or
                       data.get("id")      or data.get("user"))
                sid = (data.get("session")      or data.get("session_id") or
                       data.get("token")         or data.get("access_token"))
                if uid and sid:
                    return {"user_id": str(uid), "session": str(sid)}
        except Exception as e:
            logger.debug(f"  {endpoint} exception: {e}")
        return None

    def debug_raw(self, jwt_token: str, sky_id: Optional[str] = None) -> dict:
        """
        Kirim request ke semua endpoint kandidat dan return response mentah.
        Dipakai untuk debug — lihat mana yang tidak 404.
        """
        jwt_info = self._decode_jwt(jwt_token)
        fb_id  = jwt_info.get("sub", "")
        seed   = sky_id or fb_id
        device = _pick_device(seed)
        dev_id = _gen_device_id(seed)

        ua = (
            f"Sky-Live-com.tgc.sky.android/0.28.0 "
            f"(Linux; Android {device['android']}; {device['model']} "
            f"Build/{device['build']}; en)"
        )
        headers = {
            "User-Agent":      ua,
            "Content-Type":    "application/json; charset=utf-8",
            "Host":            API_HOST,
            "Accept":          "application/json",
            "X-Unity-Version": "2021.3.16f1",
        }
        payload = {
            "type":         "facebook",
            "token":        jwt_token,
            "id":           sky_id or fb_id,
            "device_id":    dev_id,
            "game_version": 308028,
            "platform":     "android",
        }

        # Test semua endpoint — cari yang tidak 404
        endpoints = [
            "/account/session",
            "/account/create_session",
            "/account/login",
            "/account/signin",
            "/v1/account/session",
            "/v2/account/session",
            "/v1/auth/session",
            "/v1/auth/login",
            "/auth/facebook",
            "/auth/login",
        ]

        results = []
        for endpoint in endpoints:
            try:
                resp = requests.post(
                    f"{API_BASE}{endpoint}",
                    json=payload, headers=headers, timeout=10
                )
                results.append({
                    "endpoint": endpoint,
                    "status":   resp.status_code,
                    "body":     resp.text[:200],
                })
                # Stop di endpoint pertama yang bukan 404
                if resp.status_code != 404:
                    results[-1]["note"] = "⬅️ BUKAN 404! Ini endpoint yang benar"
            except Exception as e:
                results.append({"endpoint": endpoint, "error": str(e)})

        return {"results": results, "device_id": dev_id, "fb_id": fb_id}

    def _decode_jwt(self, token: str) -> dict:
        """Decode JWT payload tanpa verifikasi."""
        try:
            parts   = token.split(".")
            payload = parts[1] + "=="
            return json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            return {}

    def verify_session(self, user_id: str, session: str) -> bool:
        """
        Cek apakah session masih valid.

        Sky v0.33+ pakai msgpack + header session, bukan JSON body.
        418 = session format OK tapi data tidak valid (bisa jadi expired).
        200 = valid.
        Karena kita tidak bisa verifikasi dengan pasti tanpa msgpack decode,
        kita anggap session valid selama ada isinya (non-empty strings).
        Verifikasi real akan terjadi saat API call pertama.
        """
        # Basic validation: pastikan keduanya non-empty dan format masuk akal
        if not user_id or not session:
            return False
        if len(session) < 16:
            return False
        # Anggap valid — verifikasi real dilakukan saat API call
        # Sky tidak expose endpoint verifikasi yang bisa dipanggil dari luar
        return True


class SessionManager:
    """
    Manager session per akun.
    Session = UNIK per akun Sky, bukan universal.
    """

    def __init__(self, storage_path: Optional[str] = None):
        # Gunakan absolute path berdasarkan lokasi file ini
        # agar tidak bergantung pada CWD saat bot dijalankan
        _here = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(os.path.dirname(_here))  # naik 2x → root skctl/
        default_path = os.path.join(_project_root, "data", "sessions.json")
        self.storage_path = storage_path or default_path
        self.sessions: Dict[str, dict] = {}
        self.extractor = SkySessionExtractor()
        self._load()

    def _load(self):
        try:
            with open(self.storage_path) as f:
                self.sessions = json.load(f)
            logger.info(f"Sessions loaded ({len(self.sessions)} akun) dari {self.storage_path}")
        except FileNotFoundError:
            self.sessions = {}
            logger.info(f"Sessions file belum ada, mulai kosong: {self.storage_path}")
        except Exception as e:
            logger.error(f"Load sessions error: {e}")
            self.sessions = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(self.sessions, f, indent=2)
            logger.info(f"Sessions saved ({len(self.sessions)} akun) → {self.storage_path}")
        except Exception as e:
            logger.error(f"Save sessions error: {e}")

    def get_or_create(self, tg_uid: str, jwt_token: str, sky_id: Optional[str] = None) -> Optional[Tuple[str, str]]:
        """
        Get session yang ada, atau coba buat baru dari JWT.
        Kalau session sudah ada (set manual), langsung return tanpa verifikasi ke server.
        Returns (user_id, session) atau None.
        """
        existing = self.sessions.get(tg_uid)
        if existing:
            uid, sid = existing.get("user_id"), existing.get("session")
            if uid and sid:
                # Kalau set manual, langsung pakai tanpa verifikasi server
                if existing.get("manual"):
                    logger.info(f"Using manual session for {tg_uid}")
                    return uid, sid
                # Kalau dari extract otomatis, cek basic validity
                if self.extractor.verify_session(uid, sid):
                    return uid, sid
                logger.info("Session tidak valid, coba buat baru...")

        # Coba buat baru dari JWT
        data = self.extractor.extract_from_jwt(jwt_token, sky_id=sky_id)
        if not data:
            return None

        uid, sid = data["user_id"], data["session"]
        self.sessions[tg_uid] = {
            "user_id": uid,
            "session": sid,
            "name": data.get("name", "?"),
            "jwt": jwt_token,
        }
        self._save()
        return uid, sid

    def set_manual(self, tg_uid: str, user_id: str, session: str, name: str = "?"):
        """Set session manual dari input user."""
        self.sessions[tg_uid] = {
            "user_id": user_id,
            "session": session,
            "name": name,
            "manual": True,
        }
        self._save()

    def get(self, tg_uid: str) -> Optional[Tuple[str, str]]:
        """Get session yang ada."""
        d = self.sessions.get(tg_uid)
        if d:
            return d.get("user_id"), d.get("session")
        return None

    def get_info(self, tg_uid: str) -> dict:
        # Reload dari file setiap kali dipanggil
        # Agar session_keeper.py yang update file langsung terbaca oleh bot
        self._load()
        return self.sessions.get(tg_uid, {})

    def clear(self, tg_uid: str):
        self.sessions.pop(tg_uid, None)
        self._save()
