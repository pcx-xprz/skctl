# 📍 Coordinate-Based Auto CR Guide

## 🎯 Overview

Bot sekarang support **TWO MODES**:

### 1. **Computer Vision Mode** (requires game running)
- Uses OpenCV to detect candles in real-time
- Requires game screen access
- Dynamic pathfinding
- More flexible but needs display

### 2. **Coordinate Mode** ✨ NEW & RECOMMENDED
- Uses pre-recorded waypoints
- **NO GAME NEEDED for testing!**
- Works in WSL2/headless environments
- Faster and more reliable
- Can be developed WITHOUT owning the game!

---

## 🚀 Coordinate Mode - How It Works

### Concept

Instead of detecting candles via computer vision, bot follows **pre-recorded paths** dengan coordinates:

```python
Waypoint(x=960, y=540, action="move", duration=2.0, description="Start position")
Waypoint(x=850, y=500, action="collect", duration=1.5, description="First candle")
Waypoint(x=800, y=450, action="collect", duration=1.0, description="Second candle")
# ... and so on
```

### Advantages

✅ **No computer vision needed** - No screen capture, no image processing  
✅ **Works without game** - Can test logic without Sky:CotL installed  
✅ **WSL2 compatible** - No X11/display required  
✅ **Faster execution** - Direct coordinates, no detection delay  
✅ **Consistent results** - Same path every time  
✅ **Easier to develop** - Just JSON coordinates!  
✅ **Community shareable** - Share route files!  

### Disadvantages

⚠️ Routes need to be recorded first (by someone with game)  
⚠️ Game updates may break coordinates  
⚠️ Less flexible than CV mode  

---

## 📋 Using Coordinate Mode

### List Available Routes

```
/routes
```

Output:
```
📍 Available Candle Run Routes:

1. Prairie Village Run
   🗺️ Realm: Prairie
   ⭐ Difficulty: easy
   🕯️ Candles: ~15
   ⏱️ Time: ~5 min
   📍 Waypoints: 19
   /run Prairie Village Run

2. Isle Dawn Simple
   🗺️ Realm: Isle
   ⭐ Difficulty: easy
   🕯️ Candles: ~8
   ⏱️ Time: ~3 min
   📍 Waypoints: 12
   /run Isle Dawn Simple

3. Forest Candle Run
   🗺️ Realm: Forest
   ⭐ Difficulty: medium
   🕯️ Candles: ~20
   ⏱️ Time: ~7 min
   📍 Waypoints: 25
   /run Forest Candle Run
```

### Run a Route

```
/run Prairie Village Run
```

Bot will:
1. Load the route from `data/routes/prairie_village_run.json`
2. Execute each waypoint sequentially
3. Send progress updates every 5 waypoints
4. Report final statistics

### Stop a Route

```
/stop
```

---

## 🛠️ Creating Your Own Routes

### Method 1: Manual JSON Creation

Create file in `data/routes/my_route.json`:

```json
{
  "name": "My Custom Route",
  "realm": "Prairie",
  "difficulty": "easy",
  "estimated_candles": 10,
  "estimated_time": 240,
  "waypoints": [
    {
      "x": 960,
      "y": 540,
      "action": "move",
      "duration": 2.0,
      "description": "Start at spawn"
    },
    {
      "x": 900,
      "y": 500,
      "action": "collect",
      "duration": 1.5,
      "description": "First candle"
    },
    {
      "x": 850,
      "y": 480,
      "action": "fly",
      "duration": 3.0,
      "description": "Fly to platform"
    }
  ]
}
```

### Method 2: Record from Game (Future Feature)

```python
# Start recording
recorder = RouteRecorder()
recorder.start("My Route")

# Play game normally, bot records your movements
# Every candle collected = waypoint added

# Stop and save
recorder.stop()
recorder.save("data/routes/my_route.json")
```

### Method 3: Import from Community

Download community routes:

```bash
# Download from repository or community
wget https://example.com/routes/expert_prairie_run.json -P data/routes/

# Reload bot to load new routes
```

---

## 📐 Waypoint Actions

### Available Actions:

| Action | Description | Parameters |
|--------|-------------|------------|
| `move` | Move character to coordinate | `x, y, duration` |
| `collect` | Move + collect candle | `x, y, duration` |
| `interact` | Interact with object | `duration` |
| `fly` | Fly to coordinate | `x, y, duration` |
| `wait` | Wait/pause | `duration` |

### Action Examples:

```python
# Move to position
Waypoint(x=800, y=600, action="move", duration=2.0)

# Collect candle
Waypoint(x=750, y=580, action="collect", duration=1.5)

# Interact with door/spirit
Waypoint(x=0, y=0, action="interact", duration=0.5)

# Fly upward
Waypoint(x=800, y=400, action="fly", duration=3.0)

# Wait for loading/animation
Waypoint(x=0, y=0, action="wait", duration=2.0)
```

---

## 🎮 Coordinate System

### Screen Coordinates

Assumes standard 1920x1080 resolution:

```
(0,0)                    (1920,0)
  ┌────────────────────────┐
  │                        │
  │       (960,540)        │  ← Center
  │          •             │
  │                        │
  └────────────────────────┘
(0,1080)              (1920,1080)
```

### Finding Coordinates

**Method 1: Screenshot + Paint**
1. Take game screenshot
2. Open in Paint/GIMP
3. Hover over candle locations
4. Note coordinates

**Method 2: Mouse Position Logger**
```python
import pyautogui
while True:
    x, y = pyautogui.position()
    print(f"Position: ({x}, {y})")
    time.sleep(0.5)
```

**Method 3: Game Overlay Tool** (future)
- Run overlay that shows coordinates
- Click candle positions to record

---

## 📊 Route Statistics

Bot tracks:
- ✅ Waypoints completed
- 🕯️ Candles collected
- ⏱️ Time elapsed
- 📍 Current position
- 📈 Progress percentage

View stats:
```
/stats
```

---

## 🌐 Community Routes

### Sharing Routes

Share your route files:

```bash
# Export route
cat data/routes/my_awesome_route.json

# Share on GitHub/Discord/Forum
```

### Importing Routes

```bash
# Download route file
curl -o data/routes/expert_run.json https://example.com/routes/expert_run.json

# Restart bot to load
python main.py
```

### Route Repository (Future)

Planned features:
- Central route repository
- Rating system
- Auto-update routes
- Community contributions
- Route verification

---

## 🔧 Advanced: Route Optimization

### Tools for Creating Routes:

1. **Route Planner** (future)
   - Visual map interface
   - Drag-drop waypoints
   - Auto-calculate optimal path
   - Export to JSON

2. **Route Analyzer**
   - Analyze efficiency
   - Suggest improvements
   - Detect missing candles
   - Calculate time estimates

3. **Route Merger**
   - Combine multiple routes
   - Create full-realm runs
   - Optimize transitions

---

## 💡 Development Without Game

YES! You can develop routes without owning Sky:CotL!

### How:

1. **Use sample routes** - Bot includes 3 sample routes
2. **Test logic** - All route execution logic works without game
3. **Simulate** - Bot has test mode that simulates movement
4. **Community data** - Get coordinates from community

### Example Test:

```bash
# Run in test mode (no game needed)
python -c "
from automation.coordinate_runner import setup_sample_routes

runner = setup_sample_routes()
print('Available routes:', runner.list_routes())

# Test route loading
route = runner.get_route('Prairie Village Run')
print(f'Loaded {route.name} with {len(route.waypoints)} waypoints')
"
```

---

## 🎯 Real-World Usage

### Scenario 1: You HAVE the game

1. Record your own routes while playing
2. Share with community
3. Use CV mode for dynamic runs
4. Use coordinate mode for speed runs

### Scenario 2: You DON'T have the game

1. Use community routes
2. Develop/test bot logic
3. Contribute code improvements
4. Create tools (planners, analyzers)
5. **Bot works fine for testing!**

---

## 🚀 Getting Started (Without Game)

```bash
# 1. Clone & setup
git clone https://github.com/pcx-xprz/skctl.git
cd skctl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your TELEGRAM_BOT_TOKEN

# 3. Run bot
python main.py

# 4. In Telegram
/start
/login  # Get auth token
/routes  # See sample routes
/run Prairie Village Run  # Test coordinate system!
```

Bot will execute route logic even without game!

---

## 📖 Sample Routes Included

Bot includes 3 ready-to-use routes:

1. **Prairie Village Run**
   - Perfect for beginners
   - 15 candles, ~5 minutes
   - 19 waypoints
   - Easy difficulty

2. **Isle Dawn Simple**
   - Quick run
   - 8 candles, ~3 minutes
   - 12 waypoints
   - Beginner friendly

3. **Forest Candle Run**
   - Advanced route
   - 20 candles, ~7 minutes
   - 25 waypoints
   - Includes flying sections

---

## ❓ FAQ

**Q: Do I need the game installed?**  
A: No! Coordinate mode works without game for testing.

**Q: Will coordinates work on my resolution?**  
A: Routes assume 1920x1080. Need scaling for other resolutions (future feature).

**Q: Can I use CV mode and coordinate mode together?**  
A: Yes! CV for exploration, coordinates for farming.

**Q: How do I get coordinates if I don't have game?**  
A: Use community routes or ask community to record.

**Q: What if game updates?**  
A: Coordinates may need adjustment. Community will update routes.

---

## 🎉 Summary

✅ **Coordinate mode = No game needed for development!**  
✅ **Pre-recorded paths are faster and more reliable**  
✅ **Perfect for WSL2/headless environments**  
✅ **Community can share and improve routes**  
✅ **You can contribute even without owning Sky:CotL!**  

Use `/routes` to get started! 🚀
