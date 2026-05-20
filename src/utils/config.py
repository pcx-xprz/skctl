"""
Configuration utilities
"""

import os
from dotenv import load_dotenv
from typing import Tuple

load_dotenv()


class Config:
    """Configuration class"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID', '')
    
    # Sky CoTL
    SKY_AUTH_URL = os.getenv('SKY_AUTH_URL', 'https://live.radiance.thatgamecompany.com')
    SKY_OAUTH_ENDPOINT = os.getenv('SKY_OAUTH_ENDPOINT', '/account/auth/oauth_signin')
    
    # Facebook OAuth
    FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', '2937460447670 69')
    FACEBOOK_OAUTH_URL = os.getenv('FACEBOOK_OAUTH_URL', 'https://www.facebook.com/v18.0/dialog/oauth')
    
    # Game Settings
    GAME_WINDOW_TITLE = os.getenv('GAME_WINDOW_TITLE', 'Sky: Children of the Light')
    AUTO_CR_INTERVAL = int(os.getenv('AUTO_CR_INTERVAL', '300'))
    MAX_CANDLES_PER_RUN = int(os.getenv('MAX_CANDLES_PER_RUN', '20'))
    
    # Computer Vision
    @staticmethod
    def get_hsv_lower() -> Tuple[int, int, int]:
        """Get HSV lower bound"""
        values = os.getenv('CANDLE_HSV_LOWER', '10,100,100').split(',')
        return tuple(map(int, values))
    
    @staticmethod
    def get_hsv_upper() -> Tuple[int, int, int]:
        """Get HSV upper bound"""
        values = os.getenv('CANDLE_HSV_UPPER', '30,255,255').split(',')
        return tuple(map(int, values))
    
    DETECTION_CONFIDENCE = float(os.getenv('DETECTION_CONFIDENCE', '0.75'))
    
    # Debug
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    SAVE_SCREENSHOTS = os.getenv('SAVE_SCREENSHOTS', 'True').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            return False
        return True
