# 📦 Installation Guide - Sky Auto CR Bot

## Prerequisites

### System Requirements
- Python 3.9 or higher
- Windows/Linux/MacOS
- 4GB RAM minimum
- Active internet connection

### Game Requirements
- Sky: Children of the Light installed
- Game running in windowed mode (recommended)
- Facebook account linked to Sky account

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/pcx-xprz/skctl.git
cd skctl
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/MacOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Configure Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` dengan text editor favorit kamu:

```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# Your Telegram User ID (optional, for admin features)
TELEGRAM_ADMIN_ID=123456789

# Leave others as default
```

### 6. Get Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow instructions to create bot
4. Copy the token provided
5. Paste token di `.env` file

### 7. Test Installation

```bash
python main.py
```

You should see:
```
╔══════════════════════════════════════════════════════════╗
║        🌟 Sky: Children of the Light 🌟                 ║
║               Auto Candle Run Bot                        ║
╚══════════════════════════════════════════════════════════╝

✅ Bot initialized successfully
🚀 Starting bot polling...
```

## 🔧 Troubleshooting

### Issue: ModuleNotFoundError

**Solution:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Playwright browsers not found

**Solution:**
```bash
playwright install chromium
```

### Issue: Permission denied

**Solution (Linux/MacOS):**
```bash
chmod +x main.py
```

### Issue: Bot tidak merespon di Telegram

**Check:**
1. Token benar di `.env`
2. Bot running dengan `python main.py`
3. Sudah /start bot di Telegram

## 🎮 Game Setup

### Windows Mode (Recommended)

1. Launch Sky: Children of the Light
2. Go to Settings
3. Set to **Windowed Mode** atau **Borderless Window**
4. Resolution: 1920x1080 (recommended) atau 1280x720
5. Graphics: Medium/High (agar candles terlihat jelas)

### Multi-Monitor Setup

Jika punya multiple monitors:
- Run game di **primary monitor**
- Bot akan auto-detect primary monitor
- Atau edit `src/cv/candle_detector.py` line untuk specify monitor

## 📱 Android Setup (Advanced)

Bot juga support Android via ADB:

### Install ADB
```bash
# Windows: Download from Android SDK Platform Tools
# Linux:
sudo apt-get install android-tools-adb

# MacOS:
brew install android-platform-tools
```

### Enable USB Debugging
1. Settings → About Phone → Tap "Build Number" 7x
2. Settings → Developer Options → Enable USB Debugging
3. Connect device via USB

### Test ADB
```bash
adb devices
```

## 🐳 Docker (Optional)

Run bot in Docker container:

```bash
docker build -t sky-auto-cr .
docker run -it --env-file .env sky-auto-cr
```

## 🚀 Quick Start

After installation:

1. **Start bot:**
   ```bash
   python main.py
   ```

2. **Open Telegram** dan cari bot kamu

3. **Send `/start`** untuk begin

4. **Login** dengan `/login`

5. **Start Auto CR** dengan `/autocr`

## 📝 Notes

- First run akan download Playwright browser (~100MB)
- Bot needs to stay running di background
- Game harus visible (not minimized)
- Recommended: Run on dedicated machine

## ⚠️ Security

- Never share your `.env` file
- Token is sensitive data
- Use bot responsibly
- Risk of account ban!

## 💡 Tips

1. Test di alt account dulu
2. Jangan run 24/7
3. Monitor bot occasionally
4. Use /stop before closing game
5. Keep game in windowed mode

## 📞 Support

Issues? Check:
- GitHub Issues: `https://github.com/pcx-xprz/skctl/issues`
- Telegram: Contact bot admin
- Wiki: Full documentation

Happy botting! 🌟
