# 📖 Usage Guide - Sky Auto CR Bot

## 🎯 Quick Start

### 1. Persiapan

**Before starting bot:**
- ✅ Game sudah running
- ✅ Character ada di area candle run (Isle, Prairie, Forest, Valley, Wasteland, Vault)
- ✅ Game dalam windowed mode
- ✅ Sudah login via Telegram

### 2. Start Bot

```bash
python main.py
```

Bot akan ready ketika muncul:
```
🚀 Starting bot polling...
```

### 3. Telegram Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Mulai bot dan welcome message | `/start` |
| `/help` | List semua commands | `/help` |
| `/login` | Proses Facebook OAuth login | `/login` |
| `/status` | Check login status & bot info | `/status` |
| `/autocr` | **Start auto candle run** | `/autocr` |
| `/stop` | **Stop auto candle run** | `/stop` |
| `/stats` | View session statistics | `/stats` |
| `/screenshot` | Take screenshot with detection overlay | `/screenshot` |

## 🔐 Login Process (Detail)

### Method 1: Manual (Seperti FengWu Bot) - RECOMMENDED

1. **Send `/login` di Telegram**
   
2. **Klik link yang bot kirim:**
   ```
   https://live.radiance.thatgamecompany.com/account/auth/oauth_signin?type=Facebook&token=
   ```

3. **Login dengan Facebook:**
   - Gunakan Facebook account yang sudah linked ke Sky
   - Authorize application jika diminta
   
4. **Copy JWT Token:**
   Browser akan menampilkan token seperti ini:
   ```json
   {
     "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImI2ZjlhNWU1..."
   }
   ```
   
   Copy **HANYA bagian token** (yang dimulai dengan `eyJ...`)

5. **Paste di Telegram:**
   ```
   eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImI2ZjlhNWU1NmFjYTdhNTkzMzA0NTgwNTM0NDA2MDI5OTlhNGE0Y2QifQ.eyJpc3MiOiJodHRwczpcL1wvd3d3LmZhY2Vib29rLmNvbSIsImF1ZCI6IjI5Mzc0NjA0NDc2NzA2OSIsInN1YiI6IjIzNzIyMzY1ODYzODIwOSIsImlhdCI6MTc2NDc3MDIzNywiZXhwIjoxNzY0NzczODM3...
   ```

6. **Bot will validate:**
   ```
   ✅ Login Berhasil!
   👤 Welcome, [Your Name]!
   ```

### Method 2: Automated (Beta)

⚠️ Warning: Bisa terdeteksi sebagai bot oleh Facebook!

```python
# Edit src/auth/oauth_handler.py untuk enable
# Tidak direkomendasikan untuk production
```

## 🎮 Auto Candle Run

### Starting Auto CR

1. **Position character** di area dengan candles
   - Recommended: Prairie (Daylight Prairie) - banyak candles
   - Valley Race track - efficient route
   - Isle of Dawn - beginner friendly

2. **Send `/autocr` di Telegram**

3. **Bot will:**
   - 🔍 Scan screen untuk candles
   - 🎯 Prioritize nearest candle
   - 🚶 Navigate ke candle location
   - 🕯️ Collect candle
   - 🔄 Repeat

### Monitoring Progress

**Real-time updates:**
```
🕯️ Progress: 10 candles collected!
🕯️ Progress: 20 candles collected!
...
```

**Check stats anytime:**
```
/stats
```

Output:
```
📊 Auto CR Statistics

🟢 Status: Running
🕯️ Candles: 23
📏 Distance: 15,432px
📍 Visited: 47 positions
```

### Stopping Auto CR

**Method 1: Command**
```
/stop
```

**Method 2: Emergency**
- Move mouse ke screen corner (PyAutoGUI failsafe)
- Press `Ctrl+C` di terminal

### Best Practices

#### ✅ DO:
- Start di area dengan banyak candles visible
- Keep game window focused
- Monitor bot occasionally
- Use `/screenshot` to check detection
- Stop bot when moving to different realm

#### ❌ DON'T:
- Minimize game window
- Switch to different window
- Start in empty areas
- Run 24/7 continuously
- Use on main account without caution

## 📊 Understanding Statistics

### Stats Breakdown

```
📊 Auto CR Statistics

🟢 Status: Running           ← Bot currently active
🕯️ Candles: 23              ← Total candles collected this session
📏 Distance: 15,432px        ← Total distance traveled
📍 Visited: 47 positions     ← Unique positions visited

⏱️ Session Info:
• Average distance/candle: 671px
```

### Performance Metrics

**Good Performance:**
- Average distance/candle: < 500px (efficient pathing)
- Collection rate: ~2-5 candles/minute

**Poor Performance:**
- Average distance/candle: > 1000px (character might be stuck)
- Collection rate: < 1 candle/minute (bad area or detection issues)

## 🐛 Troubleshooting

### Bot tidak detect candles

**Check:**
1. Game graphics settings (candles harus visible)
2. Time of day in-game (some candles only appear certain times)
3. Camera angle (candles should be visible on screen)
4. Use `/screenshot` to see what bot sees

**Fix:**
```python
# Adjust HSV values in .env if needed
CANDLE_HSV_LOWER=10,100,100
CANDLE_HSV_UPPER=30,255,255
```

### Character stuck

Bot has auto-recovery, but you can:
1. Send `/stop`
2. Manually move character
3. Send `/autocr` again

### False detections

Bot might detect:
- Torches (similar color)
- Fire (similar glow)
- Other light sources

**Solution:**
- Move to cleaner area
- Adjust confidence threshold in config

### Token expired

```
❌ Token expired!
```

**Fix:**
1. Send `/login` again
2. Get new JWT token
3. Paste in Telegram

Tokens expire after ~3 hours.

## 🎯 Advanced Usage

### Custom HSV Tuning

For different lighting conditions:

1. Take screenshot with `/screenshot`
2. Analyze candle colors
3. Adjust in `.env`:

```env
# Brighter environment
CANDLE_HSV_LOWER=5,80,150
CANDLE_HSV_UPPER=35,255,255

# Darker environment
CANDLE_HSV_LOWER=15,120,80
CANDLE_HSV_UPPER=25,255,200
```

### Area-Specific Strategies

**Prairie (Daylight Prairie):**
```
Best route: Start from entrance → Butterfly field → Village → Caves
Expected: 15-25 candles per run
```

**Golden Wasteland:**
```
More challenging due to dark environment
Adjust HSV for darker scenes
Expected: 10-15 candles per run
```

**Valley of Triumph:**
```
Race track is most efficient
Expected: 20-30 candles per run
```

### Multi-Account Setup

Run multiple instances:

```bash
# Terminal 1
TELEGRAM_BOT_TOKEN=bot1_token python main.py

# Terminal 2
TELEGRAM_BOT_TOKEN=bot2_token python main.py
```

Each bot tracks separate users.

## 📸 Screenshot Analysis

Use `/screenshot` to debug:

**What you'll see:**
- Green boxes around detected candles
- Confidence scores
- Distance to each candle
- Numbered priority (1 = nearest)

**Reading the output:**
```
#1 d:234 c:0.87    ← Candle #1, distance 234px, confidence 87%
#2 d:456 c:0.72    ← Candle #2, distance 456px, confidence 72%
```

## ⚡ Performance Tips

### Optimize Detection Speed

1. **Lower game resolution** (less pixels to process)
2. **Close background apps** (more CPU for bot)
3. **Use medium graphics** (candles still visible but faster)

### Optimize Collection Rate

1. **Choose populated areas**
2. **Stay in open spaces** (easier pathfinding)
3. **Avoid crowded areas** (other players might collect first)

### Battery/Resource Saving

1. **Lower FPS in game settings**
2. **Reduce detection frequency** (edit code to add delays)
3. **Use headless mode for Playwright** (saves RAM)

## 📈 Expected Results

### Typical Session (1 hour)

**Good conditions:**
- 40-80 candles collected
- ~1 candle per minute
- Minimal stuck events

**Poor conditions:**
- 10-30 candles collected
- Frequent stuck events
- Need manual intervention

### Daily Candle Run

Complete daily candles (all realms):
- Estimated time: 45-90 minutes with bot
- Manual time: 60-120 minutes
- Time saved: ~20-40%

## 🔒 Safety Tips

1. **Don't run continuously** - Take breaks
2. **Vary your patterns** - Don't bot same time every day
3. **Mix with manual play** - Show human behavior
4. **Use alt account first** - Test before main
5. **Monitor ToS updates** - Stay informed

## 💬 Community

Share your experience:
- GitHub Discussions
- Telegram group (if available)
- Discord server (if available)

Happy candle running! 🕯️✨
