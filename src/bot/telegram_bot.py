"""
Telegram Bot untuk Sky Auto CR
Interface untuk user control bot melalui Telegram
"""

import asyncio
import logging
import os
from typing import Optional, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from datetime import datetime
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.oauth_handler import SkyOAuthHandler, TokenManager
from cv.candle_detector import CandleDetector
from automation.game_controller import GameController, AutoCRController

logger = logging.getLogger(__name__)


class SkyAutoBot:
    """Main Telegram bot class"""
    
    def __init__(self, token: str):
        self.token = token
        self.app = None
        
        # Initialize components
        self.oauth_handler = SkyOAuthHandler()
        self.token_manager = TokenManager()
        self.candle_detector = CandleDetector()
        self.game_controller = GameController()
        
        # User sessions
        self.user_sessions: Dict[int, dict] = {}
        
        # Auto CR controllers per user
        self.auto_cr_controllers: Dict[int, AutoCRController] = {}
        
    async def initialize(self):
        """Initialize bot"""
        self.app = Application.builder().token(self.token).build()
        
        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("login", self.cmd_login))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("autocr", self.cmd_autocr))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("screenshot", self.cmd_screenshot))
        
        # Message handler untuk token input
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handle_message
        ))
        
        # Callback query handler untuk inline buttons
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("Bot initialized successfully")
        
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        
        welcome_message = f"""
🌟 <b>Selamat datang di Sky Auto CR Bot!</b> 🌟

Halo {username}! 👋

Bot ini membantu kamu untuk melakukan Auto Candle Run di Sky: Children of the Light.

<b>📋 Cara Menggunakan:</b>

1️⃣ <b>Login</b>
   Gunakan /login untuk memulai proses login

2️⃣ <b>Auto CR</b>
   Gunakan /autocr untuk mulai auto candle run

3️⃣ <b>Status</b>
   Gunakan /status untuk cek status bot

4️⃣ <b>Stop</b>
   Gunakan /stop untuk menghentikan auto CR

<b>⚠️ PERINGATAN:</b>
• Bot ini melanggar ToS dari ThatGameCompany
• Risiko: Account BAN permanent
• Gunakan dengan tanggung jawab sendiri
• Untuk tujuan edukasi/research saja

Ketik /help untuk melihat semua commands!
"""
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='HTML'
        )
        
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
<b>📚 Daftar Commands:</b>

/start - Mulai bot dan lihat welcome message
/help - Tampilkan bantuan ini
/login - Proses login dengan Facebook OAuth
/status - Cek status login dan bot
/autocr - Mulai auto candle run
/stop - Stop auto candle run
/stats - Lihat statistik CR
/screenshot - Ambil screenshot current detection

<b>🔐 Proses Login:</b>

1. Ketik /login
2. Klik link yang diberikan bot
3. Login dengan Facebook
4. Copy JWT token yang muncul
5. Paste token di chat

<b>💡 Tips:</b>

• Pastikan game sudah running sebelum /autocr
• Bot akan detect candles otomatis
• Gunakan /stop kapan saja untuk berhenti
• Check /stats untuk monitor progress

<b>⚡ Auto CR Features:</b>

✅ Computer vision untuk detect candles
✅ Pathfinding otomatis
✅ Obstacle avoidance
✅ Real-time progress updates
✅ Statistics tracking

Butuh bantuan? Contact admin! 👨‍💻
"""
        
        await update.message.reply_text(
            help_text,
            parse_mode='HTML'
        )
        
    async def cmd_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /login command"""
        user_id = update.effective_user.id
        
        # Generate OAuth URL
        oauth_url = await self.oauth_handler.get_facebook_oauth_url()
        
        login_message = f"""
🔐 <b>Login ke Sky: Children of the Light</b>

<b>Step 1:</b> Klik link di bawah ini
👉 <a href="{oauth_url}">LOGIN WITH FACEBOOK</a>

<b>Step 2:</b> Login dengan Facebook account kamu yang sudah di-link ke Sky

<b>Step 3:</b> Setelah login berhasil, kamu akan melihat JWT token (kode panjang yang dimulai dengan "eyJ...")

<b>Step 4:</b> Copy JWT token tersebut

<b>Step 5:</b> Paste token di chat ini

<b>Contoh token:</b>
<code>eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI...</code>

⏰ Token valid selama beberapa jam
🔒 Token kamu aman dan ter-enkripsi

Tunggu instruksi dari bot setelah kamu paste tokennya! 🚀
"""
        
        # Set user state to waiting for token
        self.user_sessions[user_id] = {
            'state': 'waiting_token',
            'timestamp': datetime.now()
        }
        
        await update.message.reply_text(
            login_message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        # Check if user has token
        token = self.token_manager.get_token(str(user_id))
        token_data = self.token_manager.get_token_data(str(user_id))
        
        if token:
            # Check expiry
            is_expired = self.oauth_handler.is_token_expired(token_data)
            expiry = self.oauth_handler.get_token_expiry(token_data)
            
            status_icon = "✅" if not is_expired else "❌"
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S") if expiry else "Unknown"
            
            # Check Auto CR status
            is_running = user_id in self.auto_cr_controllers and self.auto_cr_controllers[user_id].is_running
            cr_status = "🟢 Running" if is_running else "⚪ Stopped"
            
            status_message = f"""
📊 <b>Status Bot</b>

🔐 <b>Login Status:</b> {status_icon}
👤 <b>User:</b> {token_data.get('name', 'Unknown')}
⏰ <b>Token Expiry:</b> {expiry_str}
🎮 <b>Auto CR:</b> {cr_status}

<b>📈 Detection Settings:</b>
• Candle HSV Range: [{self.candle_detector.hsv_lower[0]}-{self.candle_detector.hsv_upper[0]}]
• Min Area: {self.candle_detector.min_area}px
• Max Area: {self.candle_detector.max_area}px

Bot siap digunakan! ✨
"""
        else:
            status_message = """
📊 <b>Status Bot</b>

🔐 <b>Login Status:</b> ❌ Not logged in

Gunakan /login untuk memulai! 🚀
"""
        
        await update.message.reply_text(
            status_message,
            parse_mode='HTML'
        )
        
    async def cmd_autocr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /autocr command"""
        user_id = update.effective_user.id
        
        # Check if logged in
        token = self.token_manager.get_token(str(user_id))
        if not token:
            await update.message.reply_text(
                "❌ Kamu belum login! Gunakan /login terlebih dahulu.",
                parse_mode='HTML'
            )
            return
            
        # Check if already running
        if user_id in self.auto_cr_controllers and self.auto_cr_controllers[user_id].is_running:
            await update.message.reply_text(
                "⚠️ Auto CR sudah berjalan! Gunakan /stop untuk menghentikan.",
                parse_mode='HTML'
            )
            return
            
        # Start Auto CR
        await update.message.reply_text(
            "🚀 <b>Memulai Auto Candle Run...</b>\n\nPastikan game sudah running!",
            parse_mode='HTML'
        )
        
        # Create controller
        if user_id not in self.auto_cr_controllers:
            self.auto_cr_controllers[user_id] = AutoCRController(self.game_controller)
            
        controller = self.auto_cr_controllers[user_id]
        controller.start()
        
        # Start CR loop in background
        asyncio.create_task(self._auto_cr_loop(user_id, update))
        
        await update.message.reply_text(
            "✅ <b>Auto CR Started!</b>\n\n🎮 Bot sedang mencari candles...\nGunakan /stop untuk berhenti.",
            parse_mode='HTML'
        )
        
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        user_id = update.effective_user.id
        
        if user_id in self.auto_cr_controllers:
            controller = self.auto_cr_controllers[user_id]
            controller.stop()
            
            stats = controller.get_statistics()
            
            await update.message.reply_text(
                f"""
🛑 <b>Auto CR Stopped!</b>

📊 <b>Session Statistics:</b>
🕯️ Candles Collected: {stats['candles_collected']}
📏 Distance Traveled: {stats['total_distance']:.0f}px
📍 Positions Visited: {stats['positions_visited']}

Thanks for using Sky Auto CR Bot! 🌟
""",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "⚠️ Auto CR tidak sedang berjalan.",
                parse_mode='HTML'
            )
            
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        
        if user_id in self.auto_cr_controllers:
            controller = self.auto_cr_controllers[user_id]
            stats = controller.get_statistics()
            
            status_emoji = "🟢" if stats['is_running'] else "⚪"
            
            await update.message.reply_text(
                f"""
📊 <b>Auto CR Statistics</b>

{status_emoji} <b>Status:</b> {'Running' if stats['is_running'] else 'Stopped'}

🕯️ <b>Candles:</b> {stats['candles_collected']}
📏 <b>Distance:</b> {stats['total_distance']:.1f}px
📍 <b>Visited:</b> {stats['positions_visited']} positions

⏱️ <b>Session Info:</b>
• Average distance/candle: {stats['total_distance'] / max(stats['candles_collected'], 1):.1f}px
""",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "⚠️ Belum ada session Auto CR.\nGunakan /autocr untuk memulai!",
                parse_mode='HTML'
            )
            
    async def cmd_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /screenshot command"""
        await update.message.reply_text("📸 Capturing screenshot...")
        
        try:
            # Capture screen
            screen = self.candle_detector.capture_screen()
            
            # Detect candles
            candles = self.candle_detector.detect_candles(screen)
            
            # Visualize
            vis = self.candle_detector.visualize_detections(screen, candles)
            
            # Save temporarily
            import cv2
            screenshot_path = "logs/telegram_screenshot.jpg"
            cv2.imwrite(screenshot_path, vis)
            
            # Send to user
            with open(screenshot_path, 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"🕯️ Detected: {len(candles)} candles"
                )
                
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
            
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (mainly for token input)"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if user is in token waiting state
        if user_id in self.user_sessions and self.user_sessions[user_id].get('state') == 'waiting_token':
            # Validate token format (starts with eyJ)
            if text.startswith('eyJ'):
                await update.message.reply_text("🔍 Validating token...")
                
                # Decode token
                token_data = self.oauth_handler.decode_jwt_token(text)
                
                if token_data:
                    # Save token
                    self.token_manager.add_token(str(user_id), text, token_data)
                    
                    # Clear session state
                    self.user_sessions[user_id]['state'] = 'logged_in'
                    
                    await update.message.reply_text(
                        f"""
✅ <b>Login Berhasil!</b>

👤 <b>Welcome, {token_data.get('name', 'Unknown')}!</b>

Token kamu sudah tersimpan dengan aman.

🎮 Sekarang kamu bisa menggunakan:
• /autocr - Untuk mulai auto candle run
• /status - Untuk cek status
• /help - Untuk bantuan

Have fun! 🌟
""",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text(
                        "❌ Token tidak valid! Coba lagi dengan /login"
                    )
            else:
                await update.message.reply_text(
                    "⚠️ Token harus dimulai dengan 'eyJ'. Pastikan kamu copy token yang benar!"
                )
        else:
            # Default response
            await update.message.reply_text(
                "Gunakan /help untuk melihat daftar commands! 💡"
            )
            
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        # Handle different callbacks
        # (Could add more interactive features here)
        
    async def _auto_cr_loop(self, user_id: int, update: Update):
        """
        Background loop untuk auto CR
        
        Args:
            user_id: Telegram user ID
            update: Update object untuk send messages
        """
        controller = self.auto_cr_controllers[user_id]
        last_update_time = datetime.now()
        
        try:
            while controller.is_running:
                # Capture screen
                screen = self.candle_detector.capture_screen()
                
                # Detect candles
                candle = self.candle_detector.get_nearest_candle(screen)
                
                if candle:
                    # Process candle
                    success = controller.process_candle(
                        candle.center[0],
                        candle.center[1],
                        candle.distance_from_center
                    )
                    
                    # Send update setiap 10 candles
                    if controller.candles_collected % 10 == 0:
                        stats = controller.get_statistics()
                        await update.message.reply_text(
                            f"🕯️ Progress: {stats['candles_collected']} candles collected!",
                            parse_mode='HTML'
                        )
                else:
                    # No candles found, wait a bit
                    await asyncio.sleep(1)
                    
                # Small delay
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Error in auto CR loop: {e}")
            await update.message.reply_text(
                f"❌ Auto CR error: {e}\n\nBot stopped."
            )
            controller.stop()
            
    async def run(self):
        """Run the bot"""
        await self.initialize()
        logger.info("Starting bot...")
        
        # Use run_polling with proper config for nested event loops
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        try:
            # Keep running until stopped
            import asyncio
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received stop signal")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


# Main entry point
async def main():
    """Main function"""
    # Get token from environment
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment!")
        return
        
    # Create and run bot
    bot = SkyAutoBot(bot_token)
    await bot.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())
