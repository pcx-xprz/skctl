# Sky: Children of the Light - Auto Candle Run Bot

## 📋 Analisis Mendalam Auto CR Bot

### Overview
Bot ini adalah implementasi Python untuk automation Candle Run di game Sky: Children of the Light, mirip dengan **@fengwu_bot** di Telegram.

## 🔍 Analisis Teknis

### 1. **Authentication Flow (OAuth Facebook)**

Bot Fengwu menggunakan OAuth flow dengan Facebook yang kemudian di-exchange ke JWT token dari ThatGameCompany server:

```
User → Facebook OAuth → JWT Token → Sky Game Server
```

**Proses Login:**
1. User mengakses: `https://live.radiance.thatgamecompany.com/account/auth/oauth_signin?type=Facebook&token=`
2. Facebook OAuth redirect dengan authorization code
3. Server ThatGameCompany exchange ke JWT token
4. JWT token digunakan untuk authenticate ke Sky game server

**JWT Token Structure:**
```json
{
  "iss": "https://www.facebook.com",
  "aud": "2937460447670 69",
  "sub": "user_facebook_id",
  "iat": timestamp,
  "exp": timestamp,
  "jti": "unique_jwt_id",
  "name": "User Name",
  "picture": "profile_picture_url"
}
```

### 2. **Computer Vision untuk Candle Detection**

Auto CR bot menggunakan teknik computer vision untuk:
- **Detect candles** di screen (warna orange/kuning terang)
- **Path finding** untuk navigasi character
- **Object recognition** untuk obstacle avoidance

**Library yang digunakan:**
- OpenCV (cv2) - Image processing
- PIL/Pillow - Screenshot capture
- NumPy - Array operations
- pytesseract (optional) - OCR untuk UI elements

**Candle Detection Algorithm:**
1. **Screenshot capture** dari game window
2. **Color filtering** (HSV color space untuk detect orange/yellow glow)
3. **Contour detection** untuk find candle locations
4. **Calculate path** dari character ke nearest candle
5. **Send input** (keyboard/mouse automation)

**HSV Color Range untuk Candles:**
```python
# Orange/Yellow glow dari candles
lower_candle = np.array([10, 100, 100])  # Lower HSV
upper_candle = np.array([30, 255, 255])  # Upper HSV
```

### 3. **Input Automation**

Bot menggunakan:
- **PyAutoGUI** - Mouse & keyboard automation
- **pynput** - Input control yang lebih smooth
- **ADB (Android Debug Bridge)** - Untuk Android device automation

### 4. **Telegram Bot Integration**

**python-telegram-bot library** untuk:
- User command handling (`/start`, `/login`, `/autocr`, `/stop`)
- Session management per user
- Real-time status updates
- Screenshot sharing

## 🏗️ Arsitektur Bot

```
┌─────────────────┐
│  Telegram Bot   │  ← User Interface
└────────┬────────┘
         │
    ┌────▼────┐
    │  Bot    │  ← Command Handler
    │ Manager │
    └────┬────┘
         │
    ┌────▼──────────────────┐
    │   Authentication      │  ← OAuth & JWT Handler
    │     Module            │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────┐
    │  Computer Vision      │  ← Candle Detection
    │     Engine            │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────┐
    │   Input Controller    │  ← Game Automation
    │  (PyAutoGUI/ADB)      │
    └───────────────────────┘
```

## 📦 Dependencies

```txt
python-telegram-bot==20.7
playwright==1.40.0
opencv-python==4.8.1.78
pillow==10.1.0
numpy==1.26.2
pyautogui==0.9.54
pynput==1.7.6
requests==2.31.0
pyjwt==2.8.0
cryptography==41.0.7
python-dotenv==1.0.0
aiohttp==3.9.1
```

## 🎮 Fitur Bot

### Core Features:
1. ✅ **Facebook OAuth Login** via Playwright automation
2. ✅ **JWT Token Management** dengan auto-refresh
3. ✅ **Canvas Detection** menggunakan OpenCV
4. ✅ **Auto Candle Run** dengan path optimization
5. ✅ **Multi-User Support** via Telegram
6. ✅ **Real-time Progress** reporting
7. ✅ **Screenshot Sharing** untuk verification

### Advanced Features:
- Auto-dodge obstacles
- Efficient route calculation
- Daily quest completion
- Candle farming statistics
- Schedule automation (cron-like)

## 🔐 Security Considerations

⚠️ **PENTING:**
- Bot ini melanggar ToS (Terms of Service) dari ThatGameCompany
- Risiko: **Account Ban** permanent
- Gunakan hanya untuk **research/educational purposes**
- Jangan gunakan pada main account

## 🚀 Cara Kerja Bot Fengwu

1. **Login Phase:**
   - User request login via Telegram
   - Bot provide Facebook OAuth link
   - User login & copy JWT token
   - Bot validate & store token

2. **Auto CR Phase:**
   - Bot capture game screen
   - Detect candles using color filtering
   - Calculate optimal path
   - Simulate input (movement + interaction)
   - Collect candles & avoid obstacles

3. **Monitoring Phase:**
   - Track collected candles
   - Send periodic updates to Telegram
   - Handle errors (stuck, disconnected, etc.)

## 📚 Repository References

Berdasarkan analisis GitHub repos:

1. **TheSR007/That_Sky_Mod_Release** - Mod untuk Sky CoTL PC
   - Contains injection scripts
   - Memory manipulation techniques
   
2. **thatskymod/Sky-CotL-Scripts** - Collection of automation scripts
   - Lua scripts untuk game automation
   - Memory addresses untuk hacks

3. **gxosty/gxost-script-for-Sky-CoTL** - Game scripting engine
   - Auto-farming mechanics
   - Event automation

## 🎯 Next Steps

1. ✅ Analisis selesai
2. ⏳ Implementasi OAuth handler dengan Playwright
3. ⏳ Computer vision engine untuk candle detection
4. ⏳ Input automation system
5. ⏳ Telegram bot interface
6. ⏳ Testing & optimization

---

**Disclaimer:** This project is for educational purposes only. Use at your own risk.
