"""
Main entry point untuk Sky Auto CR Bot
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from bot.telegram_bot import SkyAutoBot


def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if not exists
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


async def main():
    """Main function"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        🌟 Sky: Children of the Light 🌟                 ║
║               Auto Candle Run Bot                        ║
║                                                          ║
║  ⚠️  WARNING: This bot violates ToS!                    ║
║  🚫  Risk: PERMANENT BAN                                 ║
║  📚  For educational purposes only!                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("Starting Sky Auto CR Bot v1.0.0")
    logger.info("="*60)
    
    # Check required environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        logger.error("Please create .env file and add your bot token.")
        logger.error("Example: TELEGRAM_BOT_TOKEN=your_token_here")
        return
        
    # Create and run bot
    try:
        bot = SkyAutoBot(bot_token)
        logger.info("✅ Bot initialized successfully")
        logger.info("🚀 Starting bot polling...")
        
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
