"""
Game Controller untuk Sky: Children of the Light
Handle input automation (keyboard, mouse) untuk auto CR
"""

import pyautogui
import time
import logging
import numpy as np
from typing import Tuple, Optional, List
from enum import Enum
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

logger = logging.getLogger(__name__)


class Direction(Enum):
    """Movement directions"""
    FORWARD = "w"
    BACKWARD = "s"
    LEFT = "a"
    RIGHT = "d"
    UP = "space"  # Jump/Fly
    DOWN = "shift"  # Descend


class GameController:
    """Controller untuk game input automation"""
    
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()
        
        # Safety settings
        pyautogui.PAUSE = 0.1
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        
        # Movement settings
        self.movement_duration = 0.5  # Default movement duration
        self.turn_sensitivity = 10  # Pixels per degree
        
        # Screen center
        screen_size = pyautogui.size()
        self.screen_center = (screen_size.width // 2, screen_size.height // 2)
        
        logger.info(f"GameController initialized. Screen: {screen_size}")
        
    def move_to_position(self, x: int, y: int, duration: float = 0.5):
        """
        Move character towards position by turning camera
        
        Args:
            x, y: Target position on screen
            duration: Movement duration
        """
        # Calculate angle to target
        dx = x - self.screen_center[0]
        dy = y - self.screen_center[1]
        
        # Turn camera
        if abs(dx) > 50:  # Threshold
            self._turn_camera(dx, 0)
            
        # Move forward
        self.press_key(Direction.FORWARD, duration)
        
    def _turn_camera(self, dx: int, dy: int):
        """
        Turn camera by mouse movement
        
        Args:
            dx, dy: Delta movement
        """
        # Move mouse relative
        pyautogui.moveRel(dx, dy, duration=0.2)
        
    def press_key(self, direction: Direction, duration: float = 0.5):
        """
        Press and hold key untuk duration
        
        Args:
            direction: Direction enum
            duration: How long to hold
        """
        key = direction.value
        
        logger.debug(f"Pressing {key} for {duration}s")
        
        # Press
        if key == Key.space or key == Key.shift:
            self.keyboard.press(key)
        else:
            self.keyboard.press(key)
            
        # Hold
        time.sleep(duration)
        
        # Release
        if key == Key.space or key == Key.shift:
            self.keyboard.release(key)
        else:
            self.keyboard.release(key)
            
    def tap_key(self, key: str):
        """Quick tap key"""
        self.keyboard.press(key)
        time.sleep(0.05)
        self.keyboard.release(key)
        
    def interact(self):
        """Interact with object (usually Space key)"""
        logger.debug("Interacting...")
        self.tap_key(Key.space)
        time.sleep(0.5)
        
    def fly_towards(self, x: int, y: int, duration: float = 1.0):
        """
        Fly towards target position
        
        Args:
            x, y: Target screen position
            duration: Flight duration
        """
        # Look at target
        dx = x - self.screen_center[0]
        dy = y - self.screen_center[1]
        
        self._turn_camera(dx, dy)
        
        # Hold jump to fly
        self.keyboard.press(Key.space)
        time.sleep(duration)
        self.keyboard.release(Key.space)
        
    def navigate_to_candle(
        self, 
        candle_x: int, 
        candle_y: int,
        distance: float
    ) -> bool:
        """
        Navigate ke candle position
        
        Args:
            candle_x, candle_y: Candle screen position
            distance: Distance dari center (untuk estimate waktu)
            
        Returns:
            True jika berhasil navigate
        """
        try:
            # Calculate movement time based on distance
            move_time = min(distance / 200, 3.0)  # Max 3 seconds
            
            # Turn towards candle
            dx = candle_x - self.screen_center[0]
            self._turn_camera(dx, 0)
            time.sleep(0.3)
            
            # Move forward
            logger.info(f"Moving towards candle for {move_time:.2f}s")
            self.press_key(Direction.FORWARD, move_time)
            
            # Try to interact
            self.interact()
            
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to candle: {e}")
            return False
            
    def collect_wax(self):
        """Collect wax (biasanya otomatis, tapi bisa perlu interaction)"""
        # Wax biasanya auto-collect, tapi kadang perlu klik
        time.sleep(0.5)
        
    def emergency_stop(self):
        """Emergency stop semua movement"""
        logger.warning("EMERGENCY STOP!")
        
        # Release all keys
        for direction in Direction:
            try:
                if direction.value == Key.space or direction.value == Key.shift:
                    self.keyboard.release(direction.value)
                else:
                    self.keyboard.release(direction.value)
            except:
                pass
                
    def return_to_home(self):
        """Return to home (emergency exit)"""
        logger.info("Returning to home...")
        
        # Press ESC
        self.tap_key(Key.esc)
        time.sleep(1)
        
        # Look for Home button (would need CV to detect)
        # For now, just press ESC again
        self.tap_key(Key.esc)


class PathPlanner:
    """Path planning untuk navigasi ke candles"""
    
    def __init__(self):
        self.visited_positions: List[Tuple[int, int]] = []
        self.max_history = 100
        
    def is_stuck(self, current_pos: Tuple[int, int], threshold: int = 50) -> bool:
        """
        Check apakah character stuck di posisi yang sama
        
        Args:
            current_pos: Current position
            threshold: Distance threshold
            
        Returns:
            True jika stuck
        """
        if len(self.visited_positions) < 5:
            return False
            
        # Check last 5 positions
        recent = self.visited_positions[-5:]
        
        for pos in recent:
            dist = np.sqrt((pos[0] - current_pos[0])**2 + (pos[1] - current_pos[1])**2)
            if dist < threshold:
                return True
                
        return False
        
    def add_position(self, pos: Tuple[int, int]):
        """Add visited position"""
        self.visited_positions.append(pos)
        
        # Keep history limited
        if len(self.visited_positions) > self.max_history:
            self.visited_positions.pop(0)
            
    def get_unstuck_movement(self) -> Direction:
        """Get random movement untuk escape stuck position"""
        import random
        return random.choice([
            Direction.BACKWARD,
            Direction.LEFT,
            Direction.RIGHT
        ])
        
    def calculate_path(
        self, 
        start: Tuple[int, int], 
        end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """
        Calculate path dari start ke end
        Simple implementation: direct line
        
        Args:
            start: Start position
            end: End position
            
        Returns:
            List of waypoints
        """
        # For now, just return direct path
        # Advanced: could implement A* pathfinding
        return [start, end]


class AutoCRController:
    """Main controller untuk Auto Candle Run"""
    
    def __init__(self, game_controller: GameController):
        self.controller = game_controller
        self.path_planner = PathPlanner()
        self.is_running = False
        self.candles_collected = 0
        self.total_distance_traveled = 0.0
        
    def start(self):
        """Start auto CR"""
        self.is_running = True
        self.candles_collected = 0
        logger.info("Auto CR started")
        
    def stop(self):
        """Stop auto CR"""
        self.is_running = False
        self.controller.emergency_stop()
        logger.info(f"Auto CR stopped. Collected: {self.candles_collected} candles")
        
    def process_candle(
        self, 
        candle_x: int, 
        candle_y: int, 
        distance: float
    ) -> bool:
        """
        Process single candle
        
        Args:
            candle_x, candle_y: Candle position
            distance: Distance from center
            
        Returns:
            True jika berhasil
        """
        if not self.is_running:
            return False
            
        logger.info(f"Processing candle at ({candle_x}, {candle_y}), distance: {distance:.1f}")
        
        # Navigate to candle
        success = self.controller.navigate_to_candle(candle_x, candle_y, distance)
        
        if success:
            self.candles_collected += 1
            self.total_distance_traveled += distance
            logger.info(f"Candle collected! Total: {self.candles_collected}")
            
        # Add position to history
        self.path_planner.add_position((candle_x, candle_y))
        
        # Check if stuck
        if self.path_planner.is_stuck((candle_x, candle_y)):
            logger.warning("Character might be stuck! Attempting recovery...")
            unstuck_dir = self.path_planner.get_unstuck_movement()
            self.controller.press_key(unstuck_dir, 1.0)
            
        return success
        
    def get_statistics(self) -> dict:
        """Get auto CR statistics"""
        return {
            'candles_collected': self.candles_collected,
            'total_distance': self.total_distance_traveled,
            'is_running': self.is_running,
            'positions_visited': len(self.path_planner.visited_positions)
        }


# Test function
def test_controller():
    """Test game controller"""
    print("Testing game controller...")
    print("You have 3 seconds to focus on game window!")
    time.sleep(3)
    
    controller = GameController()
    
    # Test movement
    print("Moving forward...")
    controller.press_key(Direction.FORWARD, 2.0)
    
    time.sleep(1)
    
    print("Turning left...")
    controller.press_key(Direction.LEFT, 1.0)
    
    time.sleep(1)
    
    print("Jumping...")
    controller.interact()
    
    print("Test complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_controller()
