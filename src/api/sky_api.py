"""
Sky CoTL API Client
Reverse-engineered dari artdeell/AutoWax4C
API host: live.radiance.thatgamecompany.com
"""

import requests
import logging
import time
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

API_HOST = "live.radiance.thatgamecompany.com"
API_BASE = f"https://{API_HOST}"
USER_AGENT = "Sky-Live-com.tgc.sky.android/0.15.1.280 (unknown; android 30.0.0; en)"


class SkyAPIClient:
    """
    Client untuk Sky API.
    Bisa init dari:
    1. JWT token saja (akan auto-extract session)
    2. user_id + session_id langsung
    """

    def __init__(self, jwt_token: str,
                 user_id: Optional[str] = None,
                 session_id: Optional[str] = None):
        self.jwt_token = jwt_token
        self.session_id: Optional[str] = session_id
        self.user_id: Optional[str] = user_id
        self._parse_jwt(jwt_token)
        # Override jika diberikan langsung
        if user_id:
            self.user_id = user_id
        if session_id:
            self.session_id = session_id
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
        })

    def _parse_jwt(self, token: str):
        """Extract user info dari JWT token."""
        try:
            import base64, json
            parts = token.split(".")
            payload = parts[1] + "=="
            data = json.loads(base64.urlsafe_b64decode(payload))
            self.user_id = data.get("sub", "")
            self.facebook_name = data.get("name", "Unknown")
            logger.info(f"JWT parsed: user={self.facebook_name}, sub={self.user_id}")
        except Exception as e:
            logger.error(f"JWT parse error: {e}")

    def set_session(self, session_id: str, user_id: str):
        """Set session setelah login exchange."""
        self.session_id = session_id
        self.user_id = user_id

    def set_session(self, user_id: str, session_id: str):
        """Set session setelah berhasil extract."""
        self.user_id = user_id
        self.session_id = session_id
        logger.info(f"Session set: user={user_id[:8]}... session={session_id[:8]}...")

    def _post(self, path: str, data: dict, retries: int = 3) -> Optional[dict]:
        """POST request ke Sky API."""
        url = f"{API_BASE}{path}"
        headers = {}
        if self.session_id:
            headers["session"] = self.session_id
        if self.user_id:
            headers["user-id"] = self.user_id
        # Tambahkan Authorization header dengan JWT sebagai fallback
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        for attempt in range(retries):
            try:
                resp = self.http.post(url, json=data, headers=headers, timeout=15)
                if resp.status_code == 401:
                    logger.warning("Session expired (401)")
                    return None
                result = resp.json() if resp.text else {}
                # Handle throttle
                if result.get("result") == "throttle":
                    cooldown = result.get("cooldown", 5)
                    logger.info(f"Throttled, waiting {cooldown}s...")
                    time.sleep(cooldown)
                    continue
                # Handle timeout
                if result.get("result") == "timeout":
                    logger.info("Server timeout, retrying...")
                    time.sleep(2)
                    continue
                return result
            except Exception as e:
                logger.error(f"Request error ({attempt+1}/{retries}): {e}")
                time.sleep(1)
        return None

    def _base(self) -> dict:
        """Base payload dengan user + session."""
        return {
            "user": self.user_id or "",
            "session": self.session_id or "",
        }

    # ─── Currency ──────────────────────────────────────────────────────────────

    def get_currency(self) -> Optional[dict]:
        """Ambil currency balance (candles, wax, season_candle, season_wax)."""
        resp = self._post("/account/get_currency", self._base())
        return resp.get("currency") if resp else None

    # ─── Candle Run (Auto CR) ──────────────────────────────────────────────────

    def collect_pickup_batch(self, level_id: int, pickup_ids: List[int]) -> bool:
        """
        Collect sekelompok candles di satu level.
        Dipanggil berulang, maks 16 pickup_ids per request.
        """
        payload = self._base()
        payload["level_id"] = level_id
        payload["pickup_ids"] = pickup_ids
        resp = self._post("/account/collect_pickup_batch", payload)
        return resp is not None and resp != {}

    def do_candle_run(self, levels: List[dict], progress_cb=None) -> Tuple[int, int]:
        """
        Auto CR: collect semua candles di semua levels.
        levels = [{"level_id": int, "pickup_ids": [int, ...]}, ...]
        Returns: (total_collected, total_failed)
        """
        collected = 0
        failed = 0
        total_batches = sum(
            (len(lvl["pickup_ids"]) + 15) // 16 for lvl in levels
        )
        batch_num = 0

        for lvl in levels:
            level_id = lvl["level_id"]
            pickup_ids = lvl["pickup_ids"]

            # Kirim dalam batch 16 pickup per request
            for i in range(0, len(pickup_ids), 16):
                batch = pickup_ids[i:i+16]
                ok = self.collect_pickup_batch(level_id, batch)
                if ok:
                    collected += len(batch)
                else:
                    failed += len(batch)
                batch_num += 1
                if progress_cb:
                    progress_cb(batch_num, total_batches, collected)
                time.sleep(0.3)  # Rate limiting

        logger.info(f"CR done: collected={collected}, failed={failed}")
        return collected, failed

    # ─── Forge Wax → Candles ──────────────────────────────────────────────────

    def forge_wax(self) -> dict:
        """
        Forge wax menjadi candles.
        150 wax = 1 regular candle
        12 season_wax = 1 season candle
        Returns: dict dengan info hasil forge
        """
        result = {"regular": 0, "season": 0, "error": None}

        currency = self.get_currency()
        if not currency:
            result["error"] = "Gagal ambil currency"
            return result

        wax = currency.get("wax", 0)
        season_wax = currency.get("season_wax", 0)
        candles_before = currency.get("candles", 0)
        season_before = currency.get("season_candle", 0)

        logger.info(f"Currency: wax={wax}, season_wax={season_wax}, "
                    f"candles={candles_before}, season_candle={season_before}")

        # Forge regular wax → candles (150 wax per candle)
        if wax >= 150:
            count = wax // 150
            payload = self._base()
            payload.update({
                "currency": "candles",
                "forge_currency": "wax",
                "count": count,
                "cost": 150,
            })
            resp = self._post("/account/buy_candle_wax", payload)
            if resp and resp.get("result") == "ok":
                new_currency = resp.get("currency", {})
                result["regular"] = new_currency.get("candles", candles_before) - candles_before
                logger.info(f"Forged {result['regular']} regular candles from {wax} wax")
            else:
                result["error"] = f"Forge regular failed: {resp}"

        # Forge season wax → season candles (12 per candle)
        if season_wax >= 12:
            count = season_wax // 12
            payload = self._base()
            payload.update({
                "currency": "season_candle",
                "forge_currency": "season_wax",
                "count": count,
                "cost": 12,
            })
            resp = self._post("/account/buy_candle_wax", payload)
            if resp and resp.get("result") == "ok":
                new_currency = resp.get("currency", {})
                result["season"] = new_currency.get("season_candle", season_before) - season_before
                logger.info(f"Forged {result['season']} season candles from {season_wax} wax")

        return result

    # ─── Daily Quests ─────────────────────────────────────────────────────────

    def get_daily_quests(self) -> Optional[List[dict]]:
        """Ambil daftar daily/season quests."""
        resp = self._post("/account/get_season_quests", self._base())
        if not resp:
            return None
        return resp.get("season_quests", [])

    def claim_all_quests(self) -> dict:
        """
        Auto claim semua daily quests.
        Mirip doQuests() di AutoWax4C.
        Returns: dict statistik
        """
        result = {"activated": 0, "claimed": 0, "failed": 0, "candles": 0}

        quests = self.get_daily_quests()
        if not quests:
            result["error"] = "Gagal ambil quests"
            return result

        # Step 1: Activate all quests
        for quest in quests:
            if not quest.get("activated", True):
                payload = self._base()
                payload["quest_id"] = quest["daily_quest_def_id"]
                resp = self._post("/account/activate_season_quest", payload)
                if resp:
                    result["activated"] += 1
                    # Update quest data
                    for updated in resp.get("season_quest_activated", []):
                        if updated.get("quest_id") == quest["daily_quest_def_id"]:
                            quest["activated"] = True
                            quest["start_value"] = updated.get("start_value", 0)

        # Step 2: Claim all quests
        for quest in quests:
            if not quest.get("stat_type"):
                continue
            start_val = quest.get("start_value", 0)
            stat_delta = quest.get("stat_delta", 30)

            # Set achievement stat
            stat_payload = self._base()
            stat_payload["achievement_stats"] = [{
                "type": quest["stat_type"],
                "value": int(start_val + stat_delta),
            }]
            self._post("/account/set_achievement_stats", stat_payload)

            # Claim reward
            claim_payload = self._base()
            claim_payload["quest_id"] = quest["daily_quest_def_id"]
            resp = self._post("/account/claim_season_quest_reward", claim_payload)

            if resp:
                claim_result = resp.get("season_quest_claim_result", "")
                if claim_result in ("ok", "already"):
                    result["claimed"] += 1
                    if resp.get("currency"):
                        cur = resp["currency"]
                        result["candles"] += cur.get("candles", 0) + cur.get("season_candle", 0)
                else:
                    # Retry with higher value
                    stat_payload["achievement_stats"][0]["value"] = int(start_val + stat_delta * 2)
                    self._post("/account/set_achievement_stats", stat_payload)
                    resp2 = self._post("/account/claim_season_quest_reward", claim_payload)
                    if resp2 and resp2.get("season_quest_claim_result") in ("ok", "already"):
                        result["claimed"] += 1
                    else:
                        result["failed"] += 1
            time.sleep(0.5)

        return result

    # ─── Account Info ─────────────────────────────────────────────────────────

    def get_account_info(self) -> Optional[dict]:
        """
        Ambil info akun lengkap dari JWT + currency.
        Sky tidak punya endpoint dedicated untuk profile,
        jadi kita assembe dari berbagai endpoint.
        """
        currency = self.get_currency()
        if not currency:
            return None

        return {
            "_real": True,
            "display_name": self.facebook_name,
            "user_id": self.user_id,
            "inventory": {
                "candles": currency.get("candles", 0),
                "hearts": currency.get("hearts", 0),
                "season_candle": currency.get("season_candle", 0),
                "wax": currency.get("wax", 0),
                "season_wax": currency.get("season_wax", 0),
                "prestige": currency.get("prestige", 0),  # Ascended candles
            },
        }

    # ─── Wing Buffs / Absorb Light ────────────────────────────────────────────

    def get_wing_buffs(self) -> Optional[List[dict]]:
        """Ambil daftar wing buffs yang collected."""
        resp = self._post("/account/wing_buffs/get", self._base())
        return resp.get("wing_buffs") if resp else None

    def collect_lights(self, light_names: List[str]) -> dict:
        """Collect winged lights by name."""
        payload = self._base()
        payload["names"] = light_names
        resp = self._post("/account/wing_buffs/collect", payload)
        collected = 0
        if resp and resp.get("update_wing_buffs"):
            for wb in resp["update_wing_buffs"]:
                if wb.get("collected"):
                    collected += 1
        return {"collected": collected, "total": len(light_names)}

    def eden_run(self) -> dict:
        """
        Eden run: deposit + convert wing buffs → ascended candles.
        Mirip edemRun() di AutoWax4C.
        """
        result = {"prestige": 0, "prestige_wax": 0, "error": None}

        buffs = self.get_wing_buffs()
        if not buffs:
            result["error"] = "Gagal ambil wing buffs"
            return result

        # Deposit
        deposit_payload = self._base()
        pairs = []
        for buff in buffs:
            if buff.get("collected") and buff.get("deposit_id"):
                pairs.append([buff["name"], buff["deposit_id"]])
        if not pairs:
            result["error"] = "Tidak ada wing buffs untuk di-deposit"
            return result

        deposit_payload["name_deposit_id_pairs"] = pairs
        self._post("/account/wing_buffs/deposit", deposit_payload)

        # Convert
        resp = self._post("/account/wing_buffs/convert", self._base())
        if resp and resp.get("currency"):
            cur = resp["currency"]
            result["prestige"] = cur.get("prestige", 0)
            result["prestige_wax"] = cur.get("prestige_wax", 0)

            # Re-collect buffs setelah convert
            if resp.get("wing_buffs"):
                names = [b["name"] for b in resp["wing_buffs"]]
                self.collect_lights(names)

        return result

    # ─── Gifts ────────────────────────────────────────────────────────────────

    def get_pending_gifts(self) -> Optional[dict]:
        """Ambil pending gifts (sent + received)."""
        return self._post("/account/get_pending_messages", self._base())

    def collect_all_gifts(self) -> int:
        """Collect semua received gifts."""
        gifts = self.get_pending_gifts()
        if not gifts or not gifts.get("set_recvd_messages"):
            return 0
        collected = 0
        for gift in gifts["set_recvd_messages"]:
            payload = self._base()
            payload["msg_id"] = gift["msg_id"]
            payload["type"] = gift["type"]
            resp = self._post("/account/accept_message", payload)
            if resp:
                collected += 1
            time.sleep(0.3)
        return collected


# ─── Mock data untuk demo (tanpa API) ─────────────────────────────────────────

def get_mock_account_info() -> dict:
    return {
        "_real": False,
        "display_name": "Sky Traveler",
        "user_id": "demo_user",
        "inventory": {
            "candles": 45,
            "hearts": 12,
            "season_candle": 23,
            "wax": 3200,
            "season_wax": 84,
            "prestige": 8,
        },
    }


def get_mock_daily_quests() -> List[dict]:
    return [
        {
            "daily_quest_def_id": "quest_relive_memory",
            "title": "Relive a Memory",
            "description": "Relive a spirit memory in any realm",
            "reward": "3 Seasonal Candles",
            "activated": True,
            "completed": False,
            "progress": {"current": 0, "total": 1},
        },
        {
            "daily_quest_def_id": "quest_light_candles",
            "title": "Light 20 Candles",
            "description": "Light candles in Golden Wasteland",
            "reward": "2 Regular Candles",
            "activated": True,
            "completed": False,
            "progress": {"current": 8, "total": 20},
        },
        {
            "daily_quest_def_id": "quest_make_friends",
            "title": "Make Friends",
            "description": "Wave to 5 different players",
            "reward": "1 Heart",
            "activated": True,
            "completed": True,
            "progress": {"current": 5, "total": 5},
        },
        {
            "daily_quest_def_id": "quest_meditate",
            "title": "Meditate at Temple",
            "description": "Meditate at Geyser in Daylight Prairie",
            "reward": "5 Regular Candles",
            "activated": False,
            "completed": False,
            "progress": {"current": 0, "total": 1},
        },
    ]


def format_account_info(data: dict) -> str:
    inv = data.get("inventory", {})
    lines = [
        "👤 <b>Account Info</b>\n",
        f"📛 Name: <b>{data.get('display_name', '?')}</b>",
        f"🆔 User ID: <code>{data.get('user_id', '?')}</code>\n",
        "<b>💰 Currency:</b>",
        f"🕯️ Candles: <b>{inv.get('candles', 0)}</b>",
        f"⭐ Season Candles: <b>{inv.get('season_candle', 0)}</b>",
        f"❤️ Hearts: <b>{inv.get('hearts', 0)}</b>",
        f"💎 Ascended: <b>{inv.get('prestige', 0)}</b>\n",
        "<b>🫙 Wax:</b>",
        f"🟡 Wax: <b>{inv.get('wax', 0)}</b> ({inv.get('wax',0)//150} candles)",
        f"🟠 Season Wax: <b>{inv.get('season_wax', 0)}</b> ({inv.get('season_wax',0)//12} s.candles)",
    ]
    return "\n".join(lines)


def format_daily_quests(quests: List[dict]) -> str:
    if not quests:
        return "❌ Tidak ada daily quests"
    lines = ["<b>📋 Daily Quests</b>\n"]
    for i, q in enumerate(quests, 1):
        done = q.get("completed", False)
        icon = "✅" if done else ("⏳" if q.get("activated") else "🔒")
        lines.append(f"{icon} <b>{i}. {q.get('title', 'Quest')}</b>")
        if q.get("description"):
            lines.append(f"   📝 {q['description']}")
        if q.get("reward"):
            lines.append(f"   🎁 {q['reward']}")
        prog = q.get("progress", {})
        if prog:
            cur = prog.get("current", 0)
            tot = prog.get("total", 1)
            pct = int(cur / tot * 100) if tot else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"   [{bar}] {cur}/{tot}")
        lines.append("")
    return "\n".join(lines)
