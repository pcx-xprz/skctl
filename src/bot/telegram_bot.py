"""
Sky Auto CR Telegram Bot - Complete Version
Features: Login, Account Info, Daily Quests, All Realms Auto CR
"""

import asyncio
import logging
import os
import sys
from typing import Optional, Dict
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
    SkyAPIClient, format_account_info, format_daily_quests,
    get_mock_account_info, get_mock_daily_quests
)

logger = logging.getLogger(__name__)


class SkyAutoBot:
    def __init__(self, token: str):
        self.token = token
        self.app = None
        self.oauth_handler = SkyOAuthHandler()
        self.token_manager = TokenManager()
        self.coordinate_runner = setup_sample_routes()
        self.user_sessions: Dict[int, dict] = {}

    async def initialize(self):
        self.app = Application.builder().token(self.token).build()
        handlers = [
            ("start",      self.cmd_start),
            ("help",       self.cmd_help),
            ("login",      self.cmd_login),
            ("status",     self.cmd_status),
            ("account",    self.cmd_account),
            ("quests",     self.cmd_quests),
            ("routes",     self.cmd_routes),
            ("run",        self.cmd_run),
            ("stop",       self.cmd_stop),
            ("stats",      self.cmd_stats),
        ]
        for cmd, func in handlers:
            self.app.add_handler(CommandHandler(cmd, func))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_message
        ))
        logger.info("Bot initialized")

    # ─── /start ────────────────────────────────────────────────────────────────
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        name = update.effective_user.username or "Traveler"
        await update.message.reply_text(
            f"🌟 <b>Sky Auto CR Bot</b>\n\n"
            f"Halo <b>{name}</b>! 👋\n\n"
            f"<b>Commands:</b>\n"
            f"/login – Login via Facebook\n"
            f"/account – Info akun kamu\n"
            f"/quests – Daily quests hari ini\n"
            f"/routes – Daftar semua route\n"
            f"/run [nama] – Jalankan route\n"
            f"/stop – Hentikan route\n"
            f"/stats – Statistik session\n"
            f"/status – Status bot\n\n"
            f"⚡ <b>Coordinate mode</b> – tidak butuh game!\n"
            f"Ketik /help untuk detail.",
            parse_mode='HTML'
        )

    # ─── /help ─────────────────────────────────────────────────────────────────
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "<b>📚 Panduan Lengkap</b>\n\n"
            "<b>1. Login:</b>\n"
            "   /login → klik link → login FB → paste token\n\n"
            "<b>2. Lihat info akun:</b>\n"
            "   /account → candles, hearts, stats\n\n"
            "<b>3. Cek daily quest:</b>\n"
            "   /quests → lihat quest & progress\n\n"
            "<b>4. Auto CR semua realm:</b>\n"
            "   /routes → lihat pilihan\n"
            "   /run Complete All Realms → mulai!\n\n"
            "<b>5. Monitor & stop:</b>\n"
            "   /stats → lihat progress\n"
            "   /stop → hentikan\n\n"
            "✅ Semua route berjalan di <b>WSL tanpa game</b>!",
            parse_mode='HTML'
        )

    # ─── /login ────────────────────────────────────────────────────────────────
    async def cmd_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        oauth_url = await self.oauth_handler.get_facebook_oauth_url()
        self.user_sessions[user_id] = {'state': 'waiting_token'}
        await update.message.reply_text(
            f"🔐 <b>Login Sky CoTL</b>\n\n"
            f"<b>Step 1:</b> Buka link ini:\n"
            f"👉 <a href='{oauth_url}'>LOGIN WITH FACEBOOK</a>\n\n"
            f"<b>Step 2:</b> Login dengan Facebook\n\n"
            f"<b>Step 3:</b> Copy kode JWT (mulai <code>eyJ...</code>)\n\n"
            f"<b>Step 4:</b> Paste kode di sini ⬇️",
            parse_mode='HTML',
            disable_web_page_preview=True
        )

    # ─── /status ───────────────────────────────────────────────────────────────
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        token = self.token_manager.get_token(str(user_id))
        if token:
            td = self.token_manager.get_token_data(str(user_id))
            expired = self.oauth_handler.is_token_expired(td)
            expiry = self.oauth_handler.get_token_expiry(td)
            exp_str = expiry.strftime("%Y-%m-%d %H:%M") if expiry else "?"
            icon = "✅" if not expired else "❌"
            routes_n = len(self.coordinate_runner.list_routes())
            await update.message.reply_text(
                f"📊 <b>Status Bot</b>\n\n"
                f"🔐 Login: {icon}\n"
                f"👤 User: <b>{td.get('name','?')}</b>\n"
                f"⏰ Expire: {exp_str}\n\n"
                f"📍 Routes tersedia: {routes_n}\n"
                f"🎮 Mode: Coordinate (WSL ✅)",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ Belum login.\nGunakan /login dulu!",
                parse_mode='HTML'
            )

    # ─── /account ──────────────────────────────────────────────────────────────
    async def cmd_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        token = self.token_manager.get_token(str(user_id))
        if not token:
            await update.message.reply_text("❌ Login dulu! /login")
            return
        await update.message.reply_text("⏳ Mengambil data akun...")
        try:
            client = SkyAPIClient(token)
            data = client.get_account_info() or get_mock_account_info()
        except Exception:
            data = get_mock_account_info()
        text = format_account_info(data)
        if not data.get('_real'):
            text += "\n\n⚠️ <i>Demo data – API Sky belum publik</i>"
        await update.message.reply_text(text, parse_mode='HTML')

    # ─── /quests ───────────────────────────────────────────────────────────────
    async def cmd_quests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        token = self.token_manager.get_token(str(user_id))
        if not token:
            await update.message.reply_text("❌ Login dulu! /login")
            return
        await update.message.reply_text("⏳ Mengambil daily quests...")
        try:
            client = SkyAPIClient(token)
            quests = client.get_daily_quests() or get_mock_daily_quests()
        except Exception:
            quests = get_mock_daily_quests()
        text = format_daily_quests(quests)
        text += "\n\n⚠️ <i>Demo data – API Sky belum publik</i>"
        await update.message.reply_text(text, parse_mode='HTML')

    # ─── /routes ───────────────────────────────────────────────────────────────
    async def cmd_routes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        routes = self.coordinate_runner.list_routes()
        if not routes:
            await update.message.reply_text("❌ Tidak ada route tersedia.")
            return
        lines = ["<b>🗺️ Available Routes:</b>\n"]
        for i, name in enumerate(routes, 1):
            r = self.coordinate_runner.get_route(name)
            lines.append(
                f"<b>{i}. {r.name}</b>\n"
                f"   Realm: {r.realm} | ⭐ {r.difficulty}\n"
                f"   🕯️ ~{r.estimated_candles} candles | "
                f"⏱️ ~{r.estimated_time//60} mnt\n"
                f"   📍 {len(r.waypoints)} waypoints\n"
            )
        lines.append("💡 Ketik: <code>/run [nama route]</code>")
        await update.message.reply_text("\n".join(lines), parse_mode='HTML')

    # ─── /run ──────────────────────────────────────────────────────────────────
    async def cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        token = self.token_manager.get_token(str(user_id))
        if not token:
            await update.message.reply_text("❌ Login dulu! /login")
            return
        if not context.args:
            await update.message.reply_text(
                "⚠️ Cara pakai: <code>/run [nama route]</code>\n"
                "Contoh: <code>/run Complete All Realms</code>\n\n"
                "Lihat daftar route: /routes",
                parse_mode='HTML'
            )
            return
        route_name = ' '.join(context.args)
        route = self.coordinate_runner.get_route(route_name)
        if not route:
            await update.message.reply_text(
                f"❌ Route '<b>{route_name}</b>' tidak ditemukan!\n/routes untuk daftar.",
                parse_mode='HTML'
            )
            return
        self.coordinate_runner.start_route(route_name)
        await update.message.reply_text(
            f"🚀 <b>Memulai: {route.name}</b>\n\n"
            f"🗺️ Realm: {route.realm}\n"
            f"⭐ Difficulty: {route.difficulty}\n"
            f"🕯️ Target: ~{route.estimated_candles} candles\n"
            f"⏱️ Estimasi: ~{route.estimated_time//60} menit\n"
            f"📍 Waypoints: {len(route.waypoints)}\n\n"
            f"✨ <b>Coordinate mode ON</b> – tanpa game!\n"
            f"Gunakan /stop untuk berhenti.",
            parse_mode='HTML'
        )
        asyncio.create_task(self._run_loop(update))

    async def _run_loop(self, update: Update):
        runner = self.coordinate_runner
        last_report = 0
        try:
            while runner.is_running:
                ok, _ = runner.run_route_step(None)
                stats = runner.get_stats()
                wp = stats.get('current_waypoint', 0)
                if wp > 0 and wp % 10 == 0 and wp != last_report:
                    last_report = wp
                    await update.message.reply_text(
                        f"📊 Progress: {stats['progress']:.0f}%\n"
                        f"🕯️ Candles: {stats['candles']}/{stats['estimated_candles']}\n"
                        f"📍 Waypoint: {wp}/{stats['total_waypoints']}",
                        parse_mode='HTML'
                    )
                if not ok:
                    s = runner.get_stats()
                    await update.message.reply_text(
                        f"🎉 <b>Route Selesai!</b>\n\n"
                        f"🕯️ Candles: {s['candles']}\n"
                        f"📍 Waypoints: {s['total_waypoints']}\n\n"
                        f"GG! 🌟",
                        parse_mode='HTML'
                    )
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Route error: {e}")
            runner.stop_route()
            await update.message.reply_text(f"❌ Error: {e}")

    # ─── /stop ─────────────────────────────────────────────────────────────────
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.coordinate_runner.get_stats()
        self.coordinate_runner.stop_route()
        if stats.get('active'):
            await update.message.reply_text(
                f"🛑 <b>Route dihentikan</b>\n\n"
                f"🕯️ Candles: {stats['candles']}\n"
                f"📍 Progress: {stats['progress']:.0f}%",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("⚠️ Tidak ada route yang berjalan.")

    # ─── /stats ────────────────────────────────────────────────────────────────
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.coordinate_runner.get_stats()
        if stats.get('active'):
            await update.message.reply_text(
                f"📊 <b>Statistics</b>\n\n"
                f"🟢 Status: Running\n"
                f"🗺️ Route: {stats['route_name']}\n"
                f"🕯️ Candles: {stats['candles']}/{stats['estimated_candles']}\n"
                f"📍 Progress: {stats['progress']:.0f}%\n"
                f"📌 Waypoint: {stats['current_waypoint']}/{stats['total_waypoints']}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "⚪ Tidak ada route aktif.\nGunakan /run untuk mulai!"
            )

    # ─── Message handler ───────────────────────────────────────────────────────
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        session = self.user_sessions.get(user_id, {})
        if session.get('state') == 'waiting_token':
            if text.startswith('eyJ'):
                await update.message.reply_text("🔍 Validating token...")
                td = self.oauth_handler.decode_jwt_token(text)
                if td:
                    self.token_manager.add_token(str(user_id), text, td)
                    self.user_sessions[user_id]['state'] = 'logged_in'
                    await update.message.reply_text(
                        f"✅ <b>Login Berhasil!</b>\n\n"
                        f"👤 Welcome, <b>{td.get('name','?')}</b>!\n\n"
                        f"Coba:\n"
                        f"• /account – info akun\n"
                        f"• /quests – daily quest\n"
                        f"• /run Complete All Realms – auto CR!\n",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text("❌ Token tidak valid. Coba /login lagi.")
            else:
                await update.message.reply_text("⚠️ Token harus diawali 'eyJ...'")
        else:
            await update.message.reply_text("Ketik /help untuk bantuan 💡")

    # ─── Run bot ───────────────────────────────────────────────────────────────
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
