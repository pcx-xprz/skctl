"""
Coordinate-based Auto CR Runner
Menjalankan pre-recorded waypoints TANPA butuh game running.
Cocok untuk WSL, headless server, atau development.
"""

import json
import time
import logging
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    x: int
    y: int
    action: str = "move"
    duration: float = 1.0
    description: str = ""

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict):
        return Waypoint(
            x=d.get("x", 0),
            y=d.get("y", 0),
            action=d.get("action", "move"),
            duration=d.get("duration", 1.0),
            description=d.get("description", "")
        )


@dataclass
class CandleRoute:
    name: str
    realm: str
    difficulty: str
    estimated_candles: int
    estimated_time: int
    waypoints: List[Waypoint]

    def to_dict(self):
        return {
            "name": self.name,
            "realm": self.realm,
            "difficulty": self.difficulty,
            "estimated_candles": self.estimated_candles,
            "estimated_time": self.estimated_time,
            "waypoints": [w.to_dict() for w in self.waypoints]
        }

    @staticmethod
    def from_dict(d: dict):
        return CandleRoute(
            name=d["name"],
            realm=d["realm"],
            difficulty=d["difficulty"],
            estimated_candles=d["estimated_candles"],
            estimated_time=d["estimated_time"],
            waypoints=[Waypoint.from_dict(w) for w in d.get("waypoints", [])]
        )


class CoordinateRunner:
    """
    Runner untuk coordinate-based Auto CR.
    Tidak memerlukan screen capture atau game window.
    Berjalan di WSL / headless environment.
    """

    def __init__(self, routes_path: str = "data/routes"):
        self.routes_path = Path(routes_path)
        self.routes_path.mkdir(parents=True, exist_ok=True)
        self.routes: Dict[str, CandleRoute] = {}
        self.is_running = False
        self.current_route: Optional[CandleRoute] = None
        self.current_waypoint_index = 0
        self.candles_collected = 0
        self.load_routes()

    # ── Route management ────────────────────────────────────────────────────────

    def load_routes(self):
        """Load semua route JSON dari folder data/routes/"""
        loaded = 0
        for f in self.routes_path.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                route = CandleRoute.from_dict(data)
                self.routes[route.name] = route
                loaded += 1
                logger.info(f"Loaded route: {route.name} ({len(route.waypoints)} waypoints)")
            except Exception as e:
                logger.error(f"Failed to load {f.name}: {e}")
        logger.info(f"Total routes loaded: {loaded}")

    def save_route(self, route: CandleRoute):
        safe_name = route.name.replace(" ", "_").lower()
        path = self.routes_path / f"{safe_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(route.to_dict(), f, indent=2, ensure_ascii=False)
        self.routes[route.name] = route
        logger.info(f"Saved route: {route.name}")

    def list_routes(self) -> List[str]:
        return list(self.routes.keys())

    def get_route(self, name: str) -> Optional[CandleRoute]:
        return self.routes.get(name)

    # ── Route execution ─────────────────────────────────────────────────────────

    def start_route(self, route_name: str) -> bool:
        if route_name not in self.routes:
            logger.error(f"Route not found: {route_name}")
            return False
        self.current_route = self.routes[route_name]
        self.current_waypoint_index = 0
        self.candles_collected = 0
        self.is_running = True
        logger.info(
            f"Started: {route_name} | "
            f"{len(self.current_route.waypoints)} waypoints | "
            f"~{self.current_route.estimated_candles} candles"
        )
        return True

    def stop_route(self):
        self.is_running = False
        logger.info(f"Route stopped. Candles collected: {self.candles_collected}")

    def execute_waypoint(self, waypoint: Waypoint, game_controller=None) -> bool:
        """
        Eksekusi satu waypoint.
        game_controller bisa None (coordinate-only / WSL / API mode).

        Actions:
          move, collect, fly, interact, wait  – game input
          burn   – bakar dark plant (candle ke darkness)
          plant  – tanam/light candle di altar
          absorb – absorb wax dari candles/plants
          forge  – forge wax → candles via API
          api_cr – collect candle via Sky API langsung (tanpa game!)
        """
        desc = waypoint.description or waypoint.action
        logger.debug(f"[{waypoint.action}] ({waypoint.x},{waypoint.y}) – {desc}")

        action = waypoint.action

        # ── API-only actions (tidak butuh game) ──────────────────────────────
        if action == "api_cr":
            # Handled oleh caller (telegram_bot) via SkyAPIClient
            logger.info(f"API CR waypoint: {desc}")
            time.sleep(0.1)
            return True

        if action == "forge":
            # Handled oleh caller via SkyAPIClient.forge_wax()
            logger.info(f"Forge wax waypoint: {desc}")
            time.sleep(0.1)
            return True

        # ── Coordinate-only simulation (no game needed) ───────────────────────
        if game_controller is None:
            # Simulasi timing tanpa game
            sleep_time = min(waypoint.duration * 0.05, 0.2)
            time.sleep(sleep_time)
            if action in ("collect", "burn", "plant", "absorb"):
                self.candles_collected += 1
            return True

        # ── Real game controller ──────────────────────────────────────────────
        try:
            if action == "move":
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)

            elif action == "collect":
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                time.sleep(0.3)
                game_controller.interact()
                self.candles_collected += 1

            elif action == "burn":
                # Burn dark plant: navigate + hold candle toward darkness
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                time.sleep(0.5)
                game_controller.interact()   # Hold candle up
                time.sleep(waypoint.duration * 0.5)  # Burn duration
                game_controller.interact()   # Release
                self.candles_collected += 1
                logger.info(f"Burned dark plant at ({waypoint.x},{waypoint.y})")

            elif action == "plant":
                # Plant/light candle: navigate ke altar + interact
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                time.sleep(0.3)
                game_controller.interact()
                time.sleep(1.0)  # Wait for plant animation
                self.candles_collected += 1
                logger.info(f"Planted candle at ({waypoint.x},{waypoint.y})")

            elif action == "absorb":
                # Absorb wax: stand near candles/plants
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                time.sleep(waypoint.duration)  # Stand still to absorb
                self.candles_collected += 1
                logger.info(f"Absorbing wax at ({waypoint.x},{waypoint.y})")

            elif action == "fly":
                game_controller.fly_towards(waypoint.x, waypoint.y, waypoint.duration)

            elif action == "interact":
                game_controller.interact()

            elif action == "wait":
                time.sleep(waypoint.duration)

            else:
                logger.warning(f"Unknown action: {action}")

        except Exception as e:
            logger.warning(f"Controller error (continuing): {e}")

        return True

    def run_route_step(self, game_controller=None) -> Tuple[bool, str]:
        """
        Eksekusi satu step (satu waypoint).
        Returns: (masih_lanjut, pesan_status)
        """
        if not self.is_running or not self.current_route:
            return False, "No active route"

        if self.current_waypoint_index >= len(self.current_route.waypoints):
            self.is_running = False
            return False, f"Done! {self.candles_collected} candles collected"

        wp = self.current_route.waypoints[self.current_waypoint_index]
        self.execute_waypoint(wp, game_controller)
        self.current_waypoint_index += 1

        total = len(self.current_route.waypoints)
        pct = (self.current_waypoint_index / total) * 100
        status = (
            f"{pct:.0f}% "
            f"({self.current_waypoint_index}/{total}) "
            f"candles={self.candles_collected}"
        )
        return True, status

    def get_stats(self) -> dict:
        if not self.current_route:
            return {
                "active": False, "route_name": None,
                "progress": 0, "candles": 0,
                "estimated_candles": 0,
                "current_waypoint": 0, "total_waypoints": 0
            }
        total = len(self.current_route.waypoints)
        progress = (self.current_waypoint_index / total * 100) if total else 0
        return {
            "active": self.is_running,
            "route_name": self.current_route.name,
            "realm": self.current_route.realm,
            "progress": progress,
            "candles": self.candles_collected,
            "estimated_candles": self.current_route.estimated_candles,
            "current_waypoint": self.current_waypoint_index,
            "total_waypoints": total
        }


# ── Built-in sample routes (fallback jika JSON tidak ada) ─────────────────────

def _make_sample_routes() -> List[CandleRoute]:
    """Sample routes untuk testing tanpa file JSON."""
    isle = CandleRoute(
        name="Isle of Dawn",
        realm="Isle", difficulty="easy",
        estimated_candles=8, estimated_time=180,
        waypoints=[
            Waypoint(960, 540, "move",    1.0, "Start"),
            Waypoint(920, 520, "collect", 1.0, "Beach 1"),
            Waypoint(880, 500, "collect", 1.0, "Beach 2"),
            Waypoint(840, 480, "fly",     2.0, "Fly to temple"),
            Waypoint(800, 460, "collect", 1.0, "Temple 1"),
            Waypoint(760, 440, "collect", 1.0, "Temple 2"),
            Waypoint(720, 420, "collect", 1.0, "High candle"),
            Waypoint(960, 540, "wait",    1.0, "Done"),
        ]
    )
    prairie = CandleRoute(
        name="Prairie Village Run",
        realm="Prairie", difficulty="easy",
        estimated_candles=15, estimated_time=300,
        waypoints=[
            Waypoint(960, 540, "move",    1.0, "Start"),
            Waypoint(900, 510, "collect", 1.0, "Entrance"),
            Waypoint(860, 490, "collect", 1.0, "Butterfly 1"),
            Waypoint(820, 470, "collect", 1.0, "Butterfly 2"),
            Waypoint(780, 450, "fly",     2.0, "Village"),
            Waypoint(740, 430, "collect", 1.0, "Village 1"),
            Waypoint(700, 410, "collect", 1.0, "Village 2"),
            Waypoint(660, 390, "collect", 1.0, "Village 3"),
            Waypoint(620, 370, "collect", 1.0, "Cave 1"),
            Waypoint(580, 350, "collect", 1.0, "Cave 2"),
        ]
    )
    return [isle, prairie]


def setup_sample_routes() -> CoordinateRunner:
    """
    Inisialisasi runner.
    - Load JSON dari data/routes/ (termasuk complete_all_realms.json)
    - Jika folder kosong, tambahkan sample routes built-in
    """
    runner = CoordinateRunner()

    if not runner.routes:
        logger.info("No JSON routes found, adding built-in sample routes")
        for route in _make_sample_routes():
            runner.save_route(route)
    else:
        # Tambahkan sample jika belum ada
        existing = runner.list_routes()
        for route in _make_sample_routes():
            if route.name not in existing:
                runner.save_route(route)

    logger.info(f"Routes available: {runner.list_routes()}")
    return runner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    runner = setup_sample_routes()

    print("\n=== Available Routes ===")
    for name in runner.list_routes():
        r = runner.get_route(name)
        print(f"  {r.name}")
        print(f"    Realm: {r.realm} | Difficulty: {r.difficulty}")
        print(f"    Candles: ~{r.estimated_candles} | Time: ~{r.estimated_time//60} min")
        print(f"    Waypoints: {len(r.waypoints)}")
        print()
