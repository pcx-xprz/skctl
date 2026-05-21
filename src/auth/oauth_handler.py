"""
OAuth Handler untuk Sky: Children of the Light
Menangani Facebook OAuth flow dan JWT token management

=== FLOW OAUTH YANG TERBUKTI BEKERJA (21 Mei 2026) ===

1. GET /account/auth/oauth_signin?type=Facebook&token=
   → Redirect ke Facebook OAuth dialog

2. User login Facebook, FB POST ke /games_service/save/ dengan:
   - app_id: 293746044767069
   - redirect_uri: https://live.radiance.thatgamecompany.com/account/auth/oauth_redirect
   - state: Facebook~https://live.radiance.thatgamecompany.com/account/auth/oauth_redirect
   - scope: openid, gaming_profile

3. Facebook redirect browser ke:
   GET /account/auth/oauth_redirect?code=FB_CODE&state=Facebook~...

4. Sky server exchange code → return JSON:
   {"id":"828981538292688","alias":"Rika","token":"eyJ..."}
   → token = FB JWT (bukan session)

CATATAN PENTING:
- Response /oauth_redirect TIDAK mengandung session!
- Session hanya ada di game client binary (msgpack protocol)
- Untuk mendapat session, perlu intercept traffic game asli via mitmproxy/HTTP Toolkit
- Field yang ada di response: id (Sky ID), alias, token (FB JWT)
"""

import jwt
import json
import asyncio
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright tidak tersedia — automated browser login tidak bisa dipakai")


class SkyOAuthHandler:
    """Handler untuk Facebook OAuth authentication ke Sky CoTL"""
    
    OAUTH_REDIRECT = "https://live.radiance.thatgamecompany.com/account/auth/oauth_redirect"
    OAUTH_SIGNIN   = "https://live.radiance.thatgamecompany.com/account/auth/oauth_signin"

    def __init__(self, auth_url: str = "https://live.radiance.thatgamecompany.com"):
        self.auth_url = auth_url
        self.oauth_endpoint = "/account/auth/oauth_signin"
        self.browser = None
        self.page    = None

    async def initialize_browser(self, headless: bool = False):
        """Initialize Playwright browser"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright tidak terinstall. Jalankan: pip install playwright && playwright install chromium")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        self.page    = await self.browser.new_page()
        logger.info("Browser initialized")

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def get_facebook_oauth_url(self) -> str:
        """Generate Facebook OAuth URL untuk Sky CoTL"""
        return f"{self.auth_url}{self.oauth_endpoint}?type=Facebook&token="

    # ── CARA BARU: Exchange FB code → JSON Sky ─────────────────────────────────
    def exchange_fb_code(self, code: str) -> Optional[Dict]:
        """
        Tukar FB OAuth code dengan data Sky (id, alias, token).

        Ini adalah flow yang TERBUKTI bekerja dari reverse engineering:
        GET /account/auth/oauth_redirect?code=FB_CODE&state=Facebook~REDIRECT_URL
        → Response: {"id":"...","alias":"...","token":"eyJ..."}

        Args:
            code: Facebook OAuth authorization code

        Returns:
            Dict {"id", "alias", "token"} atau None jika gagal
        """
        state = f"Facebook~{self.OAUTH_REDIRECT}"
        try:
            resp = requests.get(
                self.OAUTH_REDIRECT,
                params={"code": code, "state": state},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/148.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json, text/html, */*",
                    "Referer": "https://web.facebook.com/",
                },
                timeout=15,
                allow_redirects=True,
            )
            logger.info(f"oauth_redirect → {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("token") and data.get("id"):
                        logger.info(f"✅ FB code exchange sukses! alias={data.get('alias')}")
                        return data
                    if data.get("error"):
                        logger.warning(f"Server error: {data['error']}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"exchange_fb_code error: {e}")
        return None
        
    async def automate_facebook_login(
        self, 
        email: str, 
        password: str
    ) -> Optional[str]:
        """
        Automate Facebook login dan extract JWT token
        
        Args:
            email: Facebook email
            password: Facebook password
            
        Returns:
            JWT token string atau None jika gagal
        """
        try:
            if not self.page:
                await self.initialize_browser(headless=False)
                
            # Navigate ke OAuth URL
            oauth_url = await self.get_facebook_oauth_url()
            logger.info(f"Navigating to: {oauth_url}")
            await self.page.goto(oauth_url, wait_until="networkidle")
            
            # Wait for Facebook login page
            await self.page.wait_for_selector('input[name="email"]', timeout=10000)
            
            # Fill credentials
            await self.page.fill('input[name="email"]', email)
            await self.page.fill('input[name="pass"]', password)
            
            # Click login button
            await self.page.click('button[name="login"]')
            
            # Wait for redirect
            await self.page.wait_for_load_state("networkidle")
            
            # Check if we need to authorize app
            try:
                continue_btn = await self.page.wait_for_selector(
                    'button[name="__CONFIRM__"]', 
                    timeout=5000
                )
                if continue_btn:
                    await continue_btn.click()
                    await self.page.wait_for_load_state("networkidle")
            except:
                pass  # Already authorized
                
            # Extract JWT token dari response
            current_url = self.page.url
            logger.info(f"Current URL after auth: {current_url}")
            
            # Token biasanya ada di URL atau di page content
            page_content = await self.page.content()
            
            # Try to extract token from page
            token = await self._extract_token_from_page(page_content)
            
            if token:
                logger.info("JWT token extracted successfully")
                return token
            else:
                logger.error("Failed to extract JWT token")
                return None
                
        except Exception as e:
            logger.error(f"Error during Facebook login automation: {e}")
            return None
            
    async def _extract_token_from_page(self, page_content: str) -> Optional[str]:
        """Extract JWT token dari page content"""
        # Token biasanya dalam format JSON atau di pre tag
        try:
            # Look for JWT pattern (3 parts separated by dots)
            import re
            jwt_pattern = r'eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*'
            matches = re.findall(jwt_pattern, page_content)
            
            if matches:
                return matches[0]
            return None
        except Exception as e:
            logger.error(f"Error extracting token: {e}")
            return None
            
    def decode_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode JWT token tanpa verifikasi (untuk inspect)
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
        """
        try:
            decoded = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
            logger.info(f"Token decoded successfully. User: {decoded.get('name', 'Unknown')}")
            return decoded
        except Exception as e:
            logger.error(f"Error decoding JWT token: {e}")
            return None
            
    def is_token_expired(self, token_data: Dict[str, Any]) -> bool:
        """Check apakah token sudah expired"""
        if 'exp' not in token_data:
            return True
            
        exp_timestamp = token_data['exp']
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        
        return datetime.now() >= exp_datetime
        
    def get_token_expiry(self, token_data: Dict[str, Any]) -> Optional[datetime]:
        """Get token expiry datetime"""
        if 'exp' in token_data:
            return datetime.fromtimestamp(token_data['exp'])
        return None
        
    async def manual_token_input(self) -> Optional[str]:
        """
        Cara manual: User login sendiri dan paste token
        Mirip dengan cara FengWu bot
        """
        if not self.page:
            await self.initialize_browser(headless=False)
            
        oauth_url = await self.get_facebook_oauth_url()
        await self.page.goto(oauth_url)
        
        print("\n" + "="*60)
        print("🔐 MANUAL LOGIN PROCESS")
        print("="*60)
        print(f"\n1. Browser window akan terbuka dengan URL:")
        print(f"   {oauth_url}")
        print(f"\n2. Login dengan Facebook account kamu")
        print(f"\n3. Setelah login, kamu akan melihat kode JWT token")
        print(f"\n4. Copy JWT token tersebut dan paste di sini")
        print("\n" + "="*60)
        
        # Wait for user to login manually
        await asyncio.sleep(5)  # Give user time to read
        
        # User akan input token via console atau Telegram
        return None  # Token akan di-input via Telegram bot


class TokenManager:
    """Manager untuk menyimpan dan manage JWT tokens"""
    
    def __init__(self, storage_path: str = "data/tokens.json"):
        self.storage_path = storage_path
        self.tokens: Dict[str, Dict] = {}
        self.load_tokens()
        
    def load_tokens(self):
        """Load tokens dari file"""
        try:
            with open(self.storage_path, 'r') as f:
                self.tokens = json.load(f)
            logger.info(f"Loaded {len(self.tokens)} tokens from storage")
        except FileNotFoundError:
            logger.info("No existing tokens file found")
            self.tokens = {}
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            self.tokens = {}
            
    def save_tokens(self):
        """Save tokens ke file"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.tokens, f, indent=2)
            logger.info("Tokens saved successfully")
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            
    def add_token(self, user_id: str, token: str, token_data: Dict):
        """Add or update token untuk user"""
        self.tokens[user_id] = {
            'token': token,
            'data': token_data,
            'added_at': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat()
        }
        self.save_tokens()
        logger.info(f"Token added for user: {user_id}")
        
    def get_token(self, user_id: str) -> Optional[str]:
        """Get token untuk user"""
        if user_id in self.tokens:
            token_info = self.tokens[user_id]
            token_info['last_used'] = datetime.now().isoformat()
            self.save_tokens()
            return token_info['token']
        return None
        
    def remove_token(self, user_id: str):
        """Remove token untuk user"""
        if user_id in self.tokens:
            del self.tokens[user_id]
            self.save_tokens()
            logger.info(f"Token removed for user: {user_id}")
            
    def get_token_data(self, user_id: str) -> Optional[Dict]:
        """Get decoded token data"""
        if user_id in self.tokens:
            return self.tokens[user_id].get('data')
        return None


# Example usage
async def test_oauth():
    """Test OAuth flow"""
    handler = SkyOAuthHandler()
    
    # Method 1: Manual (seperti FengWu bot)
    await handler.manual_token_input()
    
    # Method 2: Automated (risky, bisa kena detection)
    # token = await handler.automate_facebook_login("email@example.com", "password")
    
    await handler.close_browser()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_oauth())
