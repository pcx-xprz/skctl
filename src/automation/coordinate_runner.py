"""
Coordinate-based Auto CR
Menggunakan pre-recorded coordinates tanpa computer vision
TIDAK PERLU GAME untuk development!
"""

import time
import logging
import json
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Single waypoint/coordinate"""
    x: int
    y: int
    action: str = "move"  # move, collect, interact, wait, fly
    duration: float = 1.0
    description: str = ""
    
    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict):
        return Waypoint(**data)


@dataclass
class CandleRoute:
    """Complete route with multiple waypoints"""
    name: str
    realm: str  # Isle, Prairie, Forest, Valley, Wasteland, Vault
    difficulty: str  # easy, medium, hard
    estimated_candles: int
    estimated_time: int  # seconds
    waypoints: List[Waypoint]
    
    def to_dict(self):
        return {
            'name': self.name,
            'realm': self.realm,
            'difficulty': self.difficulty,
            'estimated_candles': self.estimated_candles,
            'estimated_time': self.estimated_time,
            'waypoints': [w.to_dict() for w in self.waypoints]
        }
    
    @staticmethod
    def from_dict(data: dict):
        waypoints = [Waypoint.from_dict(w) for w in data['waypoints']]
        return CandleRoute(
            name=data['name'],
            realm=data['realm'],
            difficulty=data['difficulty'],
            estimated_candles=data['estimated_candles'],
            estimated_time=data['estimated_time'],
            waypoints=waypoints
        )


class CoordinateRunner:
    """
    Run pre-recorded coordinate routes
    NO GAME NEEDED - Uses stored coordinates
    """
    
    def __init__(self, routes_path: str = "data/routes"):
        self.routes_path = Path(routes_path)
        self.routes_path.mkdir(parents=True, exist_ok=True)
        self.routes: Dict[str, CandleRoute] = {}
        self.is_running = False
        self.current_route: Optional[CandleRoute] = None
        self.current_waypoint_index = 0
        self.candles_collected = 0
        
        # Load existing routes
        self.load_routes()
        
    def load_routes(self):
        """Load all saved routes"""
        for route_file in self.routes_path.glob("*.json"):
            try:
                with open(route_file, 'r') as f:
                    data = json.load(f)
                    route = CandleRoute.from_dict(data)
                    self.routes[route.name] = route
                    logger.info(f"Loaded route: {route.name}")
            except Exception as e:
                logger.error(f"Error loading route {route_file}: {e}")
                
    def save_route(self, route: CandleRoute):
        """Save route to file"""
        filepath = self.routes_path / f"{route.name.replace(' ', '_').lower()}.json"
        try:
            with open(filepath, 'w') as f:
                json.dump(route.to_dict(), f, indent=2)
            self.routes[route.name] = route
            logger.info(f"Saved route: {route.name}")
        except Exception as e:
            logger.error(f"Error saving route: {e}")
            
    def list_routes(self) -> List[str]:
        """Get list of available routes"""
        return list(self.routes.keys())
        
    def get_route(self, name: str) -> Optional[CandleRoute]:
        """Get specific route"""
        return self.routes.get(name)
        
    def start_route(self, route_name: str) -> bool:
        """Start running a route"""
        if route_name not in self.routes:
            logger.error(f"Route not found: {route_name}")
            return False
            
        self.current_route = self.routes[route_name]
        self.current_waypoint_index = 0
        self.candles_collected = 0
        self.is_running = True
        
        logger.info(f"Started route: {route_name}")
        logger.info(f"Waypoints: {len(self.current_route.waypoints)}")
        logger.info(f"Estimated candles: {self.current_route.estimated_candles}")
        
        return True
        
    def stop_route(self):
        """Stop current route"""
        self.is_running = False
        logger.info("Route stopped")
        
    def execute_waypoint(self, waypoint: Waypoint, game_controller) -> bool:
        """
        Execute single waypoint action
        
        Args:
            waypoint: Waypoint to execute
            game_controller: GameController instance for input
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Executing: {waypoint.description or waypoint.action} at ({waypoint.x}, {waypoint.y})")
            
            if waypoint.action == "move":
                # Move to coordinate
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                
            elif waypoint.action == "collect":
                # Move and collect candle
                game_controller.move_to_position(waypoint.x, waypoint.y, waypoint.duration)
                time.sleep(0.3)
                game_controller.interact()
                self.candles_collected += 1
                logger.info(f"Collected candle! Total: {self.candles_collected}")
                
            elif waypoint.action == "interact":
                # Just interact (door, spirit, etc)
                game_controller.interact()
                
            elif waypoint.action == "fly":
                # Fly to coordinate
                game_controller.fly_towards(waypoint.x, waypoint.y, waypoint.duration)
                
            elif waypoint.action == "wait":
                # Just wait (loading, animation, etc)
                logger.info(f"Waiting {waypoint.duration}s...")
                time.sleep(waypoint.duration)
                
            else:
                logger.warning(f"Unknown action: {waypoint.action}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error executing waypoint: {e}")
            return False
            
    def run_route_step(self, game_controller) -> Tuple[bool, str]:
        """
        Execute one step of route
        
        Returns:
            (continue, status_message)
        """
        if not self.is_running or not self.current_route:
            return (False, "No active route")
            
        if self.current_waypoint_index >= len(self.current_route.waypoints):
            self.is_running = False
            return (False, f"Route complete! Collected {self.candles_collected} candles")
            
        # Get current waypoint
        waypoint = self.current_route.waypoints[self.current_waypoint_index]
        
        # Execute
        success = self.execute_waypoint(waypoint, game_controller)
        
        if success:
            self.current_waypoint_index += 1
            progress = (self.current_waypoint_index / len(self.current_route.waypoints)) * 100
            status = f"Progress: {progress:.1f}% ({self.current_waypoint_index}/{len(self.current_route.waypoints)})"
            return (True, status)
        else:
            return (True, "Waypoint failed, retrying...")
            
    def get_stats(self) -> Dict:
        """Get current run statistics"""
        if not self.current_route:
            return {
                'active': False,
                'route_name': None,
                'progress': 0,
                'candles': 0
            }
            
        total_waypoints = len(self.current_route.waypoints)
        progress = (self.current_waypoint_index / total_waypoints) * 100 if total_waypoints > 0 else 0
        
        return {
            'active': self.is_running,
            'route_name': self.current_route.name,
            'realm': self.current_route.realm,
            'progress': progress,
            'current_waypoint': self.current_waypoint_index,
            'total_waypoints': total_waypoints,
            'candles': self.candles_collected,
            'estimated_candles': self.current_route.estimated_candles
        }


# =====================================================
# PRE-DEFINED ROUTES
# Ini contoh routes yang bisa dipakai tanpa game!
# =====================================================

def create_sample_routes():
    """Create sample routes for testing"""
    
    # Route 1: Prairie Village (Easy)
    prairie_village = CandleRoute(
        name="Prairie Village Run",
        realm="Prairie",
        difficulty="easy",
        estimated_candles=15,
        estimated_time=300,  # 5 minutes
        waypoints=[
            Waypoint(960, 540, "move", 2.0, "Start at Prairie entrance"),
            Waypoint(850, 500, "collect", 1.5, "Candle near entrance"),
            Waypoint(800, 450, "collect", 1.0, "Candle by tree"),
            Waypoint(750, 400, "move", 2.0, "Move to village"),
            Waypoint(700, 420, "collect", 1.0, "Village candle 1"),
            Waypoint(650, 440, "collect", 1.0, "Village candle 2"),
            Waypoint(600, 460, "collect", 1.0, "Village candle 3"),
            Waypoint(700, 500, "fly", 3.0, "Fly to hill"),
            Waypoint(750, 450, "collect", 1.0, "Hill candle 1"),
            Waypoint(800, 430, "collect", 1.0, "Hill candle 2"),
            Waypoint(850, 480, "move", 2.0, "Move to cave"),
            Waypoint(820, 500, "collect", 1.0, "Cave entrance candle"),
            Waypoint(790, 520, "interact", 0.5, "Enter cave"),
            Waypoint(760, 540, "wait", 2.0, "Wait for load"),
            Waypoint(730, 520, "collect", 1.0, "Cave candle 1"),
            Waypoint(700, 500, "collect", 1.0, "Cave candle 2"),
            Waypoint(670, 480, "collect", 1.0, "Cave candle 3"),
            Waypoint(640, 460, "collect", 1.0, "Cave candle 4"),
            Waypoint(960, 540, "move", 3.0, "Return to center"),
        ]
    )
    
    # Route 2: Isle of Dawn (Beginner)
    isle_dawn = CandleRoute(
        name="Isle Dawn Simple",
        realm="Isle",
        difficulty="easy",
        estimated_candles=8,
        estimated_time=180,  # 3 minutes
        waypoints=[
            Waypoint(960, 540, "move", 1.0, "Start at spawn"),
            Waypoint(920, 520, "collect", 1.0, "First candle"),
            Waypoint(880, 500, "collect", 1.0, "Second candle"),
            Waypoint(840, 480, "move", 2.0, "Move forward"),
            Waypoint(800, 460, "collect", 1.0, "Third candle"),
            Waypoint(760, 440, "fly", 2.0, "Fly up"),
            Waypoint(720, 420, "collect", 1.0, "High candle"),
            Waypoint(780, 460, "move", 2.0, "Move to temple"),
            Waypoint(820, 480, "collect", 1.0, "Temple candle 1"),
            Waypoint(860, 500, "collect", 1.0, "Temple candle 2"),
            Waypoint(900, 520, "collect", 1.0, "Temple candle 3"),
            Waypoint(960, 540, "move", 2.0, "Return to spawn"),
        ]
    )
    
    # Route 3: Forest (Medium)
    forest_run = CandleRoute(
        name="Forest Candle Run",
        realm="Forest",
        difficulty="medium",
        estimated_candles=20,
        estimated_time=420,  # 7 minutes
        waypoints=[
            Waypoint(960, 540, "move", 2.0, "Forest entrance"),
            Waypoint(900, 500, "collect", 1.0, "Entry candle"),
            Waypoint(850, 480, "move", 2.0, "Move to treehouse"),
            Waypoint(800, 460, "fly", 3.0, "Fly to first treehouse"),
            Waypoint(780, 450, "collect", 1.0, "Treehouse candle 1"),
            Waypoint(760, 440, "collect", 1.0, "Treehouse candle 2"),
            Waypoint(820, 480, "fly", 2.0, "Fly to second treehouse"),
            Waypoint(840, 490, "collect", 1.0, "Treehouse candle 3"),
            Waypoint(860, 500, "collect", 1.0, "Treehouse candle 4"),
            Waypoint(900, 520, "move", 3.0, "Move to ground"),
            Waypoint(920, 530, "collect", 1.0, "Ground candle 1"),
            Waypoint(940, 540, "collect", 1.0, "Ground candle 2"),
            Waypoint(880, 500, "move", 2.0, "Move to brook"),
            Waypoint(850, 490, "collect", 1.0, "Brook candle 1"),
            Waypoint(820, 480, "collect", 1.0, "Brook candle 2"),
            Waypoint(790, 470, "collect", 1.0, "Brook candle 3"),
            Waypoint(760, 460, "move", 2.0, "Move to temple"),
            Waypoint(740, 450, "interact", 0.5, "Enter temple"),
            Waypoint(720, 440, "wait", 2.0, "Wait for load"),
            Waypoint(700, 430, "collect", 1.0, "Temple candle 1"),
            Waypoint(680, 420, "collect", 1.0, "Temple candle 2"),
            Waypoint(660, 410, "collect", 1.0, "Temple candle 3"),
            Waypoint(640, 400, "collect", 1.0, "Temple candle 4"),
            Waypoint(620, 390, "collect", 1.0, "Temple candle 5"),
            Waypoint(960, 540, "move", 5.0, "Return to start"),
        ]
    )
    
    return [prairie_village, isle_dawn, forest_run]


# Initialize and save sample routes
def setup_sample_routes():
    """Setup sample routes for testing"""
    runner = CoordinateRunner()
    
    for route in create_sample_routes():
        runner.save_route(route)
        
    logger.info(f"Created {len(create_sample_routes())} sample routes")
    return runner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create sample routes
    runner = setup_sample_routes()
    
    # List available routes
    print("\n📍 Available Routes:")
    for i, route_name in enumerate(runner.list_routes(), 1):
        route = runner.get_route(route_name)
        print(f"{i}. {route_name}")
        print(f"   Realm: {route.realm}")
        print(f"   Difficulty: {route.difficulty}")
        print(f"   Candles: {route.estimated_candles}")
        print(f"   Time: {route.estimated_time}s")
        print(f"   Waypoints: {len(route.waypoints)}")
        print()
