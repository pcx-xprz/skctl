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

import requests
import logging
import json
import base64
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

API_HOST  = "live.radiance.thatgamecompany.com"
API_BASE  = f"https://{API_HOST}"
# User-Agent dari AutoWax4C initWithParameters()
USER_AGENT = "Sky-Live-com.tgc.sky.android/0.15.1.280 (unknown; android 30.0.0; en)"


class SkySessionExtractor:
    """
    Mengambil session_id + user_id dari JWT Facebook token.
    Tidak perlu game terbuka!
    """

    def __init__(self):
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
            "Host": API_HOST,
        })

    def extract_from_jwt(self, jwt_token: str, sky_id: Optional[str] = None) -> Optional[Dict]:
        """
        JWT Facebook → POST create_session → {user_id, session}

        sky_id: Sky UUID dari JSON OAuth response (opsional, memperkuat request)
        Returns dict atau None.
        """
        jwt_info = self._decode_jwt(jwt_token)
        logger.info(f"JWT: name={jwt_info.get('name','?')}, sub={jwt_info.get('sub','?')}")

        # Gunakan sky_id dari JSON OAuth jika tersedia, fallback ke sub dari JWT
        fb_id = sky_id or jwt_info.get("sub", "")

        # Daftar endpoint yang dicoba (dari reverse-engineering AutoWax4C + analisis FengWu)
        # FengWu mendapat UUID langsung dari Sky OAuth page → kemungkinan besar flow-nya:
        # Sky OAuth → return { id (Sky UUID), alias, token (FB JWT) }
        # Lalu token + sky UUID dikirim ke create_session
        attempts = [
            # Cara paling mirip FengWu: kirim token + sky id
            ("/account/create_session", {
                "type": "facebook",
                "token": jwt_token,
                "id": fb_id,
                "game_version": 280,
            }),
            # AutoWax4C style: hanya token + game_version
            ("/account/create_session", {
                "type": "facebook",
                "token": jwt_token,
                "game_version": 280,
            }),
            # Variasi tanpa game_version
            ("/account/create_session", {
                "type": "facebook",
                "token": jwt_token,
            }),
            # Dengan access_token key
            ("/account/create_session", {
                "type": "facebook",
                "access_token": jwt_token,
            }),
            # Endpoint signin alternatif
            ("/account/signin", {
                "auth_token": jwt_token,
                "auth_type": "facebook",
            }),
        ]

        for endpoint, payload in attempts:
            result = self._try_endpoint(endpoint, payload)
            if result:
                result["name"] = jwt_info.get("name", "Unknown")
                result["facebook_id"] = fb_id
                logger.info(f"Session created via {endpoint}!")
                return result

        logger.warning("All session endpoints failed - session creation may require game client")
        return None

    def _try_endpoint(self, endpoint: str, payload: dict) -> Optional[Dict]:
        """Coba satu endpoint."""
        try:
            resp = self.http.post(
                f"{API_BASE}{endpoint}",
                json=payload,
                timeout=15
            )
            logger.debug(f"POST {endpoint} → {resp.status_code}: {resp.text[:150]}")

            if resp.status_code in (200, 201):
                data = resp.json()
                uid = (data.get("user_id") or data.get("userId") or
                       data.get("id") or data.get("user"))
                sid = (data.get("session") or data.get("session_id") or
                       data.get("token") or data.get("access_token"))
                if uid and sid:
                    return {"user_id": str(uid), "session": str(sid)}
        except Exception as e:
            logger.debug(f"{endpoint} error: {e}")
        return None

    def _decode_jwt(self, token: str) -> dict:
        """Decode JWT payload tanpa verifikasi."""
        try:
            parts = token.split(".")
            payload = parts[1] + "=="
            return json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            return {}

    def verify_session(self, user_id: str, session: str) -> bool:
        """Cek apakah session masih valid."""
        try:
            resp = self.http.post(
                f"{API_BASE}/account/get_currency",
                json={"user": user_id, "session": session},
                headers={"session": session, "user-id": user_id},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return "currency" in data or "result" in data
            elif resp.status_code == 401:
                return False
        except Exception:
            pass
        return False


class SessionManager:
    """
    Manager session per akun.
    Session = UNIK per akun Sky, bukan universal.
    """

    def __init__(self, storage_path: str = "data/sessions.json"):
        self.storage_path = storage_path
        self.sessions: Dict[str, dict] = {}
        self.extractor = SkySessionExtractor()
        self._load()

    def _load(self):
        try:
            with open(self.storage_path) as f:
                self.sessions = json.load(f)
        except FileNotFoundError:
            self.sessions = {}
        except Exception as e:
            logger.error(f"Load sessions: {e}")

    def _save(self):
        try:
            import os; os.makedirs("data", exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Save sessions: {e}")

    def get_or_create(self, tg_uid: str, jwt_token: str, sky_id: Optional[str] = None) -> Optional[Tuple[str, str]]:
        """
        Get session yang ada, atau buat baru dari JWT.
        sky_id: Sky UUID dari JSON OAuth (opsional, meningkatkan peluang berhasil).
        Returns (user_id, session) atau None.
        """
        existing = self.sessions.get(tg_uid)
        if existing:
            uid, sid = existing.get("user_id"), existing.get("session")
            if uid and sid:
                if self.extractor.verify_session(uid, sid):
                    return uid, sid
                logger.info("Session expired, refreshing...")

        # Buat baru
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
        return self.sessions.get(tg_uid, {})

    def clear(self, tg_uid: str):
        self.sessions.pop(tg_uid, None)
        self._save()
