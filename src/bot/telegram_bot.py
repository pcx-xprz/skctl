"""
Sky Auto CR Bot - Telegram Interface
Commands: /login /account /quests /cr /wax /forge /quests_claim /eden /gifts /routes /run /stop /stats
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Optional
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.oauth_handler import SkyOAuthHandler, TokenManager
from automation.coordinate_runner import CoordinateRunner, setup_sample_routes
from api.sky_api import (
    SkyAPIClient,
    format_account_info, format_daily_quests,
    get_mock_account_info, get_mock_daily_quests,
)
from auth.session_extractor import SessionManager, SkySessionExtractor

logger = logging.getLogger(__name__)



def _get_api(token_manager: TokenManager, user_id: int) -> Optional[SkyAPIClient]:
    """Buat SkyAPIClient dari token tersimpan."""
    token = token_manager.get_token(str(user_id))
    if not token:
        return None
    return SkyAPIClient(token)


class SkyAutoBot:
    def __init__(self, token: str):
        self.token = token
        self.app = None
        self.oauth = SkyOAuthHandler()
        self.tokens = TokenManager()
        self.session_mgr = SessionManager()    # Sky API session manager
        self.runner = setup_sample_routes()
        self.user_sessions: Dict[int, dict] = {}  # login state per user
        self._cr_tasks: Dict[int, asyncio.Task] = {}

    async def initialize(self):
        self.app = Application.builder().token(self.token).build()
        cmds = [
            ("start",        self.cmd_start),
            ("help",         self.cmd_help),
            ("login",        self.cmd_login),
            ("status",       self.cmd_status),
            ("session",      self.cmd_session),    # ← NEW
            ("account",      self.cmd_account),
            ("quests",       self.cmd_quests),
            ("cr",           self.cmd_cr),
            ("wax",          self.cmd_wax),
            ("forge",        self.cmd_forge),
            ("quests_claim", self.cmd_quests_claim),
            ("eden",         self.cmd_eden),
            ("gifts",        self.cmd_gifts),
            ("routes",       self.cmd_routes),
            ("run",          self.cmd_run),
            ("stop",         self.cmd_stop),
            ("stats",        self.cmd_stats),
            ("debug",        self.cmd_debug),   # ← debug response server Sky
        ]
        for name, handler in cmds:
            self.app.add_handler(CommandHandler(name, handler))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        logger.info("Bot initialized")



    # ─── Helper: buat API client dengan session ────────────────────────────────
    async def _get_api_client(self, tg_uid: int) -> Optional[SkyAPIClient]:
        token = self.tokens.get_token(str(tg_uid))

        # Coba ambil session yang sudah ada dulu (tanpa perlu JWT)
        info = self.session_mgr.get_info(str(tg_uid))
        if info and info.get("user_id") and info.get("session"):
            uid = info["user_id"]
            sid = info["session"]
            return SkyAPIClient(token or "", user_id=uid, session_id=sid)

        # Kalau tidak ada session dan ada token, coba create
        if not token:
            return None
        result = self.session_mgr.get_or_create(str(tg_uid), token)
        if result:
            user_id, session_id = result
            return SkyAPIClient(token, user_id=user_id, session_id=session_id)
        return SkyAPIClient(token)

    async def cmd_session(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        args = c.args
        if args and args[0] == "set" and len(args) == 3:
            user_id, session_id = args[1], args[2]
            self.session_mgr.set_manual(str(uid), user_id, session_id)
            # Session disimpan — langsung konfirmasi tanpa verifikasi server
            await u.message.reply_text(
                f"✅ <b>Session berhasil di-set!</b>\n\n"
                f"🆔 user_id: <code>{user_id}</code>\n"
                f"🔑 session: <code>{session_id[:16]}...</code>\n\n"
                f"Sekarang coba /cr atau /wax 🕯️",
                parse_mode='HTML'
            )
            return

        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return

        info = self.session_mgr.get_info(str(uid))
        if info and info.get("user_id"):
            uid_val = info["user_id"]
            sid_val = info.get("session", "?")
            extractor = SkySessionExtractor()
            is_valid = extractor.verify_session(uid_val, sid_val)
            icon = "✅" if is_valid else "❌ expired"
            await u.message.reply_text(
                f"🔑 <b>Session Info</b>\n\n"
                f"👤 Name: <b>{info.get('name','?')}</b>\n"
                f"🆔 user_id: <code>{uid_val}</code>\n"
                f"🔐 session: <code>{sid_val[:16]}...</code>\n"
                f"Status: {icon}\n\n"
                f"{'✨ Session aktif! /cr siap.' if is_valid else '⚠️ Expired. Set ulang via /session set'}",
                parse_mode='HTML'
            )
        else:
            await u.message.reply_text("⏳ Mencoba extract session...")
            result = self.session_mgr.get_or_create(str(uid), token)
            if result:
                uid_val, sid_val = result
                await u.message.reply_text(
                    f"✅ <b>Session OK!</b>\n🆔 <code>{uid_val[:16]}...</code>\n"
                    f"🔐 <code>{sid_val[:16]}...</code>\n\nCoba /cr 🎉",
                    parse_mode='HTML'
                )
            else:
                await u.message.reply_text(
                    f"⚠️ <b>Session tidak bisa di-extract otomatis</b>\n\n"
                    f"Cara manual:\n"
                    f"1. Buka game Sky di HP\n"
                    f"2. Capture traffic dengan mitmproxy/HTTP Toolkit\n"
                    f"3. Cari header <code>session</code> dan <code>user-id</code>\n"
                    f"4. Kirim: <code>/session set &lt;user_id&gt; &lt;session_id&gt;</code>\n\n"
                    f"Atau pakai /run untuk coordinate mode (tanpa session).",
                    parse_mode='HTML'
                )

    # ─── /start ────────────────────────────────────────────────────────────────
    async def cmd_start(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        name = u.effective_user.username or "Traveler"
        await u.message.reply_text(
            f"🌟 <b>Sky Auto CR Bot</b>\n\n"
            f"Halo <b>{name}</b>! 👋\n\n"
            f"<b>🔐 Auth:</b>\n"
            f"  /login – Login via Facebook\n\n"
            f"<b>📊 Info:</b>\n"
            f"  /account – Info akun & currency\n"
            f"  /quests  – Daily quests\n\n"
            f"<b>⚡ Automation (via Sky API):</b>\n"
            f"  /cr      – Auto Candle Run semua realm\n"
            f"  /wax     – Lihat wax balance\n"
            f"  /forge   – Forge wax → candles\n"
            f"  /quests_claim – Claim semua daily quest\n"
            f"  /eden    – Eden run (wax→ascended candles)\n"
            f"  /gifts   – Collect semua gifts\n\n"
            f"<b>🗺️ Coordinate Mode (tanpa game):</b>\n"
            f"  /routes  – Lihat route\n"
            f"  /run [nama] – Jalankan route\n"
            f"  /stop    – Stop route\n"
            f"  /stats   – Progress\n\n"
            f"⚠️ Untuk CR via API: butuh session ID dari game\n"
            f"Ketik /help untuk detail lengkap.",
            parse_mode='HTML'
        )

    # ─── /help ─────────────────────────────────────────────────────────────────
    async def cmd_help(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        await u.message.reply_text(
            "<b>📚 Panduan Sky Auto CR Bot</b>\n\n"
            "<b>1️⃣ Login:</b>\n"
            "   /login → klik link → login FB → paste token eyJ...\n\n"
            "<b>2️⃣ Auto CR via API (seperti AutoWax4C):</b>\n"
            "   /cr → collect semua candles semua realm via API\n"
            "   Bot kirim POST ke Sky server langsung!\n"
            "   Tidak perlu game terbuka.\n\n"
            "<b>3️⃣ Wax management:</b>\n"
            "   /wax   → lihat wax & estimasi candles\n"
            "   /forge → burn wax jadi candles\n"
            "          150 wax = 1 candle\n"
            "          12 season_wax = 1 season candle\n\n"
            "<b>4️⃣ Daily quests:</b>\n"
            "   /quests       → lihat quest hari ini\n"
            "   /quests_claim → auto claim semua reward\n\n"
            "<b>5️⃣ Eden & Gifts:</b>\n"
            "   /eden  → deposit wing buffs → ascended candles\n"
            "   /gifts → collect semua gifts dari teman\n\n"
            "<b>6️⃣ Coordinate Mode (WSL, tanpa game):</b>\n"
            "   /routes → daftar route\n"
            "   /run Complete All Realms\n\n"
            "⚠️ <b>Penting:</b> /cr butuh session aktif dari game.\n"
            "Kalau pakai WSL tanpa game, gunakan /run.",
            parse_mode='HTML'
        )



    # ─── /login ────────────────────────────────────────────────────────────────
    async def cmd_login(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        url = await self.oauth.get_facebook_oauth_url()
        self.user_sessions[uid] = {'state': 'waiting_token'}
        await u.message.reply_text(
            f"🔐 <b>Login Sky CoTL</b>\n\n"
            f"<b>Step 1:</b> Buka link berikut di browser:\n"
            f"👉 <a href='{url}'>LOGIN WITH FACEBOOK</a>\n\n"
            f"<b>Step 2:</b> Login dengan akun Facebook kamu\n\n"
            f"<b>Step 3:</b> Setelah authorize, kamu akan diarahkan ke halaman yang menampilkan JSON:\n"
            f"<code>{{\"id\":\"...\",\"alias\":\"...\",\"token\":\"eyJ...\"}}</code>\n\n"
            f"<b>Step 4:</b> Copy <b>seluruh JSON</b> tersebut dan paste di sini ⬇️\n\n"
            f"<i>💡 Bisa juga paste:</i>\n"
            f"<i>• Raw JWT token yang dimulai <code>eyJ...</code></i>\n"
            f"<i>• FB code dari URL (<code>?code=AQL...</code>) — bot akan exchange otomatis</i>\n\n"
            f"⏰ Token berlaku ~1 jam.",
            parse_mode='HTML', disable_web_page_preview=True
        )

    # ─── /status ───────────────────────────────────────────────────────────────
    async def cmd_status(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Belum login.\nGunakan /login dulu!")
            return
        td = self.tokens.get_token_data(str(uid))
        expired = self.oauth.is_token_expired(td)
        expiry = self.oauth.get_token_expiry(td)
        exp_str = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "?"
        icon = "✅" if not expired else "❌ (expired!)"
        routes_n = len(self.runner.list_routes())
        await u.message.reply_text(
            f"📊 <b>Status Bot</b>\n\n"
            f"🔐 Login: {icon}\n"
            f"👤 User: <b>{td.get('name','?')}</b>\n"
            f"⏰ Token expire: {exp_str}\n\n"
            f"📍 Routes tersedia: {routes_n}\n"
            f"🎮 Mode: API + Coordinate\n"
            f"✨ WSL Compatible: Ya\n\n"
            f"{'⚠️ Token expired, /login lagi!' if expired else '🟢 Siap! Coba /cr'}",
            parse_mode='HTML'
        )

    # ─── /account ──────────────────────────────────────────────────────────────
    async def cmd_account(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not self.tokens.get_token(str(uid)):
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text("⏳ Mengambil data akun...")
        api = await self._get_api_client(uid)
        try:
            data = api.get_account_info() if api else None
            if not data:
                data = get_mock_account_info()
        except Exception:
            data = get_mock_account_info()
        note = "" if data.get("_real") else "\n\n⚠️ <i>Demo data – butuh session aktif</i>"
        await u.message.reply_text(format_account_info(data) + note, parse_mode='HTML')

    # ─── /quests ───────────────────────────────────────────────────────────────
    async def cmd_quests(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not self.tokens.get_token(str(uid)):
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text("⏳ Mengambil daily quests...")
        api = await self._get_api_client(uid)
        try:
            quests = api.get_daily_quests() if api else None
            if not quests:
                quests = get_mock_daily_quests()
        except Exception:
            quests = get_mock_daily_quests()
        text = format_daily_quests(quests)
        text += "\n\n💡 /quests_claim untuk auto claim!"
        await u.message.reply_text(text, parse_mode='HTML')



    # ─── /cr (Auto Candle Run via API) ─────────────────────────────────────────
    async def cmd_cr(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return
        if uid in self._cr_tasks and not self._cr_tasks[uid].done():
            await u.message.reply_text("⚠️ CR sudah berjalan! /stop dulu."); return

        await u.message.reply_text(
            "🚀 <b>Auto Candle Run dimulai!</b>\n\n"
            "📡 Mode: <b>API Direct</b> (mirip AutoWax4C)\n"
            "🌐 Menghubungi Sky server...\n\n"
            "Bot akan:\n"
            "1. Collect semua candles tiap realm\n"
            "2. Forge wax → candles otomatis\n\n"
            "⏳ Estimasi: 2-5 menit...\n"
            "Gunakan /stop untuk batal.",
            parse_mode='HTML'
        )
        task = asyncio.create_task(self._cr_loop(uid, u))
        self._cr_tasks[uid] = task

    async def _cr_loop(self, uid: int, u: Update):
        """Background task: Auto CR via Sky API."""
        api = await self._get_api_client(uid)
        if not api:
            await u.message.reply_text("❌ Gagal buat API client!"); return

        if not api.session_id:
            await u.message.reply_text(
                "⚠️ <b>Session tidak ada</b>\n\n"
                "Coba:\n"
                "1. /session → auto extract session\n"
                "2. /session set &lt;uid&gt; &lt;sid&gt; → set manual\n"
                "3. /run Complete All Realms → coordinate mode (tanpa session)\n",
                parse_mode='HTML'
            )
            return

        try:
            # Import CR levels data
            import sys, os
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data'
            ))
            from cr_levels import get_all_levels
            levels = get_all_levels()
        except ImportError:
            await u.message.reply_text(
                "⚠️ <b>data/cr_levels.py tidak ditemukan!</b>\n\n"
                "Pastikan file ada. Menggunakan mode simulasi...",
                parse_mode='HTML'
            )
            levels = []

        if not levels:
            # Simulasi tanpa data
            await u.message.reply_text(
                "🎮 <b>Simulasi CR (coordinate mode)</b>\n\n"
                "Tidak ada API levels. Pakai /run untuk coordinate mode.",
                parse_mode='HTML'
            )
            return

        total_collected = 0
        total_levels = len(levels)
        realm_done = []

        def progress_cb(batch, total_batches, collected):
            pass  # Akan kirim update per realm

        await u.message.reply_text(
            f"📦 Memproses {total_levels} level area...\n"
            f"🕯️ Total pickup IDs: {sum(len(l['pickup_ids']) for l in levels)}",
            parse_mode='HTML'
        )

        for i, lvl in enumerate(levels):
            realm = lvl.get("realm", f"Level {i+1}")
            pickup_ids = lvl["pickup_ids"]
            level_id = lvl["level_id"]
            lvl_collected = 0
            lvl_failed = 0

            for j in range(0, len(pickup_ids), 16):
                batch = pickup_ids[j:j+16]
                ok = api.collect_pickup_batch(level_id, batch)
                if ok:
                    lvl_collected += len(batch)
                else:
                    lvl_failed += len(batch)
                await asyncio.sleep(0.3)

            total_collected += lvl_collected
            realm_done.append(f"✅ {realm}: {lvl_collected} wax")

            # Kirim update setiap 3 realm
            if (i + 1) % 3 == 0 or i == total_levels - 1:
                report = "\n".join(realm_done[-3:])
                await u.message.reply_text(
                    f"📊 <b>Progress CR</b>\n\n{report}\n\n"
                    f"🕯️ Total wax collected: <b>{total_collected}</b>\n"
                    f"📍 Realm: {i+1}/{total_levels}",
                    parse_mode='HTML'
                )

        # Forge wax → candles
        await u.message.reply_text("🔨 Forging wax → candles...", parse_mode='HTML')
        forge_result = api.forge_wax()

        await u.message.reply_text(
            f"🎉 <b>Auto CR Selesai!</b>\n\n"
            f"🕯️ Total wax collected: <b>{total_collected}</b>\n"
            f"🔨 Forged regular: <b>{forge_result.get('regular', 0)}</b> candles\n"
            f"⭐ Forged season: <b>{forge_result.get('season', 0)}</b> candles\n\n"
            f"{'⚠️ ' + forge_result['error'] if forge_result.get('error') else '✅ Semua berhasil!'}\n\n"
            f"Cek /account untuk balance terbaru!",
            parse_mode='HTML'
        )



    # ─── /wax ──────────────────────────────────────────────────────────────────
    async def cmd_wax(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not self.tokens.get_token(str(uid)):
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text("⏳ Mengambil wax balance...")
        api = await self._get_api_client(uid)
        currency = api.get_currency() if api else None
        if not currency:
            await u.message.reply_text(
                "⚠️ <b>Gagal ambil data currency</b>\n\n"
                "Kemungkinan:\n"
                "• Token JWT belum punya session aktif\n"
                "• Butuh login di game dulu untuk dapat session\n\n"
                "Coba /account untuk info lebih lanjut.",
                parse_mode='HTML'
            )
            return
        wax = currency.get("wax", 0)
        season_wax = currency.get("season_wax", 0)
        candles = currency.get("candles", 0)
        season_c = currency.get("season_candle", 0)
        prestige = currency.get("prestige", 0)

        await u.message.reply_text(
            f"🫙 <b>Wax Balance</b>\n\n"
            f"<b>Current:</b>\n"
            f"🟡 Wax: <b>{wax:,}</b>\n"
            f"🟠 Season Wax: <b>{season_wax:,}</b>\n\n"
            f"<b>Jika di-forge sekarang:</b>\n"
            f"🕯️ → {wax // 150:,} regular candles\n"
            f"⭐ → {season_wax // 12:,} season candles\n\n"
            f"<b>Current candles:</b>\n"
            f"🕯️ Candles: <b>{candles:,}</b>\n"
            f"⭐ Season: <b>{season_c:,}</b>\n"
            f"💎 Ascended: <b>{prestige:,}</b>\n\n"
            f"Gunakan /forge untuk burn wax!",
            parse_mode='HTML'
        )

    # ─── /forge ────────────────────────────────────────────────────────────────
    async def cmd_forge(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if not self.tokens.get_token(str(uid)):
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text(
            "🔨 <b>Forging wax → candles...</b>\n\n"
            "📐 Rate:\n• 150 wax = 1 candle\n• 12 season_wax = 1 season candle\n\n"
            "⏳ Menghubungi Sky server...", parse_mode='HTML'
        )
        api = await self._get_api_client(uid)
        if not api:
            await u.message.reply_text("❌ Gagal buat API client!"); return
        result = api.forge_wax()
        if result.get("error"):
            await u.message.reply_text(
                f"⚠️ <b>Forge gagal</b>\n\n{result['error']}\n\n"
                f"Pastikan sudah punya session aktif dari game.",
                parse_mode='HTML'
            )
        else:
            r = result.get("regular", 0)
            s = result.get("season", 0)
            await u.message.reply_text(
                f"✅ <b>Forge Berhasil!</b>\n\n"
                f"🕯️ Regular candles: +<b>{r}</b>\n"
                f"⭐ Season candles: +<b>{s}</b>\n\n"
                f"{'Tidak ada wax untuk di-forge.' if r == 0 and s == 0 else 'Balance sudah diupdate!'}\n"
                f"Cek /account untuk balance terbaru.",
                parse_mode='HTML'
            )

    # ─── /quests_claim ─────────────────────────────────────────────────────────
    async def cmd_quests_claim(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text(
            "📋 <b>Auto Claim Daily Quests</b>\n\n"
            "⏳ Mengactivate & claim semua quest...",
            parse_mode='HTML'
        )
        api = await self._get_api_client(uid)
        if not api:
            await u.message.reply_text("❌ Gagal buat API client!"); return
        result = api.claim_all_quests()
        if result.get("error"):
            await u.message.reply_text(
                f"⚠️ <b>Gagal</b>: {result['error']}", parse_mode='HTML'
            )
        else:
            await u.message.reply_text(
                f"✅ <b>Quest Claim Selesai!</b>\n\n"
                f"🔓 Activated: <b>{result.get('activated', 0)}</b>\n"
                f"🎁 Claimed: <b>{result.get('claimed', 0)}</b>\n"
                f"❌ Failed: <b>{result.get('failed', 0)}</b>\n"
                f"🕯️ Candles earned: <b>{result.get('candles', 0)}</b>\n\n"
                f"Cek /account untuk balance terbaru!",
                parse_mode='HTML'
            )



    # ─── /eden ─────────────────────────────────────────────────────────────────
    async def cmd_eden(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text(
            "🌌 <b>Eden Run</b>\n\n"
            "⏳ Depositing wing buffs...\n"
            "Ini akan convert Wing Buffs → Ascended Candles 💎",
            parse_mode='HTML'
        )
        api = await self._get_api_client(uid)
        if not api:
            await u.message.reply_text("❌ Gagal buat API client!"); return
        result = api.eden_run()
        if result.get("error"):
            await u.message.reply_text(
                f"⚠️ <b>Eden Run gagal</b>\n\n{result['error']}",
                parse_mode='HTML'
            )
        else:
            await u.message.reply_text(
                f"✅ <b>Eden Run Selesai!</b>\n\n"
                f"💎 Ascended Candles: +<b>{result.get('prestige', 0)}</b>\n"
                f"🫙 Ascended Wax: +<b>{result.get('prestige_wax', 0)}</b>\n\n"
                f"Cek /account untuk balance terbaru!",
                parse_mode='HTML'
            )

    # ─── /gifts ────────────────────────────────────────────────────────────────
    async def cmd_gifts(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return
        await u.message.reply_text("🎁 <b>Collecting semua gifts...</b>", parse_mode='HTML')
        api = await self._get_api_client(uid)
        if not api:
            await u.message.reply_text("❌ Gagal buat API client!"); return

        # Ambil pending gifts dulu
        gifts_data = api.get_pending_gifts()
        if not gifts_data:
            await u.message.reply_text(
                "⚠️ Gagal ambil gifts.\nButuh session aktif dari game.",
                parse_mode='HTML'
            )
            return

        received = gifts_data.get("set_recvd_messages", [])
        sent = gifts_data.get("set_sent_messages", [])

        collected = api.collect_all_gifts()
        await u.message.reply_text(
            f"✅ <b>Gifts Collected!</b>\n\n"
            f"📥 Gifts diterima: <b>{len(received)}</b>\n"
            f"✅ Berhasil collect: <b>{collected}</b>\n"
            f"📤 Gifts sudah terkirim: <b>{len(sent)}</b>\n\n"
            f"Cek /account untuk heart balance!",
            parse_mode='HTML'
        )

    # ─── /routes ───────────────────────────────────────────────────────────────
    async def cmd_routes(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        routes = self.runner.list_routes()
        if not routes:
            await u.message.reply_text("❌ Tidak ada route."); return
        lines = ["<b>🗺️ Available Routes</b>\n"]
        for i, name in enumerate(routes, 1):
            r = self.runner.get_route(name)
            lines.append(
                f"<b>{i}. {r.name}</b>\n"
                f"   {r.realm} | ⭐ {r.difficulty}\n"
                f"   🕯️ ~{r.estimated_candles} candles | "
                f"⏱️ ~{r.estimated_time // 60} mnt | "
                f"📍 {len(r.waypoints)} waypoints\n"
            )
        lines.append("💡 <code>/run [nama route]</code>")
        await u.message.reply_text("\n".join(lines), parse_mode='HTML')

    # ─── /debug ────────────────────────────────────────────────────────────────
    async def cmd_debug(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return

        await u.message.reply_text("🔍 <b>Debug: kirim raw request ke Sky server...</b>", parse_mode='HTML')

        sky_id = self.user_sessions.get(uid, {}).get('sky_id')
        extractor = SkySessionExtractor()
        raw = extractor.debug_raw(token, sky_id=sky_id)

        msg_parts = ["🧪 <b>Raw Response dari Sky Server:</b>\n"]
        for r in raw.get("results", []):
            ep   = r.get("endpoint", "?")
            st   = r.get("status", "ERR")
            body = r.get("body", r.get("error", "no response"))
            # Escape HTML
            body_safe = body.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            msg_parts.append(
                f"<b>Endpoint:</b> <code>{ep}</code>\n"
                f"<b>HTTP:</b> {st}\n"
                f"<b>Response:</b>\n<pre>{body_safe[:300]}</pre>\n"
            )

        msg_parts.append(
            f"\n<b>device_id dipakai:</b> <code>{raw.get('device_id','?')[:16]}...</code>\n"
            f"<b>fb_id:</b> <code>{raw.get('fb_id','?')}</code>\n\n"
            f"💡 Dari sini kita bisa tahu kenapa server reject."
        )
        await u.message.reply_text("\n".join(msg_parts), parse_mode='HTML')

    # ─── /run ──────────────────────────────────────────────────────────────────
    async def cmd_run(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        token = self.tokens.get_token(str(uid))
        if not token:
            await u.message.reply_text("❌ Login dulu! /login"); return
        if not c.args:
            await u.message.reply_text(
                "⚠️ Usage: <code>/run [nama route]</code>\n\n"
                "Lihat route tersedia: /routes\n"
                "Contoh: <code>/run Complete All Realms</code>",
                parse_mode='HTML'
            ); return
        name = ' '.join(c.args)
        route = self.runner.get_route(name)
        if not route:
            await u.message.reply_text(
                f"❌ Route '<b>{name}</b>' tidak ditemukan!\n/routes untuk daftar.",
                parse_mode='HTML'
            ); return
        self.runner.start_route(name)
        await u.message.reply_text(
            f"🚀 <b>Starting: {route.name}</b>\n\n"
            f"🗺️ {route.realm} | ⭐ {route.difficulty}\n"
            f"🕯️ ~{route.estimated_candles} candles | "
            f"⏱️ ~{route.estimated_time // 60} mnt\n"
            f"📍 {len(route.waypoints)} waypoints\n\n"
            f"✨ <b>Coordinate Mode</b> – tanpa game!\n/stop untuk berhenti.",
            parse_mode='HTML'
        )
        asyncio.create_task(self._run_loop(u))

    async def _run_loop(self, u: Update):
        runner = self.runner
        last = 0
        try:
            while runner.is_running:
                ok, _ = runner.run_route_step(None)
                stats = runner.get_stats()
                wp = stats.get('current_waypoint', 0)
                if wp > 0 and wp % 10 == 0 and wp != last:
                    last = wp
                    await u.message.reply_text(
                        f"📊 {stats['progress']:.0f}% | "
                        f"🕯️ {stats['candles']}/{stats['estimated_candles']} | "
                        f"📍 {wp}/{stats['total_waypoints']}",
                        parse_mode='HTML'
                    )
                if not ok:
                    s = runner.get_stats()
                    await u.message.reply_text(
                        f"🎉 <b>Route Selesai!</b>\n\n"
                        f"🕯️ {s['candles']} candles | 📍 {s['total_waypoints']} waypoints\n\n"
                        f"GG! 🌟",
                        parse_mode='HTML'
                    )
                    break
                await asyncio.sleep(0.3)
        except Exception as e:
            runner.stop_route()
            await u.message.reply_text(f"❌ Error: {e}")

    # ─── /stop ─────────────────────────────────────────────────────────────────
    async def cmd_stop(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        # Stop CR task
        if uid in self._cr_tasks and not self._cr_tasks[uid].done():
            self._cr_tasks[uid].cancel()
            await u.message.reply_text("🛑 Auto CR dihentikan.")
            return
        # Stop route
        stats = self.runner.get_stats()
        self.runner.stop_route()
        if stats.get('active'):
            await u.message.reply_text(
                f"🛑 <b>Route dihentikan</b>\n\n"
                f"🕯️ {stats['candles']} | 📊 {stats['progress']:.0f}%",
                parse_mode='HTML'
            )
        else:
            await u.message.reply_text("⚠️ Tidak ada yang berjalan.")

    # ─── /stats ────────────────────────────────────────────────────────────────
    async def cmd_stats(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        stats = self.runner.get_stats()
        if stats.get('active'):
            await u.message.reply_text(
                f"📊 <b>Route Statistics</b>\n\n"
                f"🟢 Running: {stats['route_name']}\n"
                f"🕯️ {stats['candles']}/{stats['estimated_candles']}\n"
                f"📊 {stats['progress']:.0f}%\n"
                f"📍 {stats['current_waypoint']}/{stats['total_waypoints']}",
                parse_mode='HTML'
            )
        else:
            await u.message.reply_text("⚪ Tidak ada route aktif.\nGunakan /run atau /cr!")



    async def handle_message(self, u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid  = u.effective_user.id
        text = u.message.text.strip()

        if self.user_sessions.get(uid, {}).get('state') != 'waiting_token':
            await u.message.reply_text("Ketik /help untuk bantuan 💡")
            return

        jwt_token = None
        sky_uuid  = None

        # ── 1. JSON lengkap {"id","alias","token"} dari oauth_redirect ────────
        if text.startswith('{'):
            try:
                import json as _j
                parsed   = _j.loads(text)
                jwt_token = parsed.get('token') or parsed.get('access_token')
                sky_uuid  = parsed.get('id')
                alias     = parsed.get('alias', 'Unknown')
                if jwt_token:
                    if sky_uuid:
                        self.user_sessions[uid]['sky_id'] = sky_uuid
                    await u.message.reply_text(
                        f"✅ JSON diterima!\n"
                        f"👤 Alias: <b>{alias}</b>\n"
                        f"🆔 Sky ID: <code>{sky_uuid}</code>\n"
                        f"🔍 Memvalidasi token...",
                        parse_mode='HTML'
                    )
            except Exception:
                pass

        # ── 2. Raw JWT token ──────────────────────────────────────────────────
        if not jwt_token and text.startswith('eyJ'):
            jwt_token = text

        # ── 3. Facebook OAuth code (AQL...) — exchange otomatis ──────────────
        #    Ini yang BARU! User tinggal copy code dari URL redirect, bukan JWT
        if not jwt_token and (text.startswith('AQL') or text.startswith('AQR') or
                               (len(text) > 100 and '-' in text and '_' in text and '.' not in text[:20])):
            await u.message.reply_text(
                "🔄 <b>Mendeteksi Facebook OAuth code...</b>\n"
                "⏳ Menukar code ke token Sky...",
                parse_mode='HTML'
            )
            sky_data = await asyncio.get_event_loop().run_in_executor(
                None, self.oauth.exchange_fb_code, text
            )
            if sky_data and sky_data.get('token'):
                jwt_token = sky_data['token']
                sky_uuid  = sky_data.get('id')
                if sky_uuid:
                    self.user_sessions[uid]['sky_id'] = sky_uuid
                await u.message.reply_text(
                    f"✅ Code berhasil ditukar!\n"
                    f"👤 Alias: <b>{sky_data.get('alias', '?')}</b>\n"
                    f"🆔 Sky ID: <code>{sky_uuid}</code>",
                    parse_mode='HTML'
                )
            else:
                await u.message.reply_text(
                    "❌ <b>Code sudah expired atau tidak valid.</b>\n\n"
                    "FB code hanya berlaku ~10 menit dan sekali pakai.\n"
                    "Coba /login lagi dan langsung paste code-nya.",
                    parse_mode='HTML'
                )
                return

        # ── Proses JWT token ──────────────────────────────────────────────────
        if jwt_token:
            td = self.oauth.decode_jwt_token(jwt_token)
            if td:
                self.tokens.add_token(str(uid), jwt_token, td)
                self.user_sessions[uid]['state'] = 'logged_in'

                await u.message.reply_text(
                    f"✅ <b>Login Berhasil!</b>\n\n"
                    f"👤 Name: <b>{td.get('name', 'Unknown')}</b>\n"
                    f"🆔 Sky ID: <code>{sky_uuid or td.get('sub','?')}</code>\n\n"
                    f"⚠️ <b>Catatan penting:</b>\n"
                    f"Bot bisa login dan menyimpan token kamu, tapi untuk fitur\n"
                    f"<b>/cr, /wax, /forge</b> butuh <b>session</b> yang hanya ada di game.\n\n"
                    f"<b>Cara dapat session (1x saja, berlaku lama):</b>\n"
                    f"1. Buka game Sky di HP\n"
                    f"2. Intercept traffic dengan <b>HTTP Toolkit</b> (httptoolkit.com)\n"
                    f"3. Filter: <code>live.radiance.thatgamecompany.com</code>\n"
                    f"4. Ambil header <code>session</code> dan <code>user-id</code>\n"
                    f"5. Kirim: <code>/session set &lt;user_id&gt; &lt;session_id&gt;</code>\n\n"
                    f"🗺️ Atau gunakan <b>/run Complete All Realms</b> (coordinate mode, tanpa session)",
                    parse_mode='HTML'
                )
            else:
                await u.message.reply_text(
                    "❌ Token tidak valid. Coba /login lagi."
                )
        else:
            await u.message.reply_text(
                "⚠️ <b>Format tidak dikenali.</b>\n\n"
                "Kirim salah satu:\n"
                "• <b>JSON</b> dari Sky OAuth: <code>{\"id\":\"...\",\"alias\":\"...\",\"token\":\"eyJ...\"}</code>\n"
                "• <b>JWT token</b>: dimulai <code>eyJ...</code>\n"
                "• <b>FB code</b>: dimulai <code>AQL...</code> (dari URL setelah login FB)\n\n"
                "💡 Cara paling mudah: setelah klik link login dan authorize FB,\n"
                "copy <b>seluruh JSON</b> yang muncul di halaman dan paste di sini.",
                parse_mode='HTML'
            )

    # ─── Run ───────────────────────────────────────────────────────────────────
    async def run(self):
        await self.initialize()
        logger.info("Bot starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


async def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN tidak ditemukan di .env!")
        return
    bot = SkyAutoBot(token)
    await bot.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
