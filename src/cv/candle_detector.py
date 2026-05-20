"""
Candle Detector menggunakan Computer Vision
Detect candles di Sky: Children of the Light menggunakan OpenCV
"""

import cv2
import numpy as np
import mss
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class CandleLocation:
    """Data class untuk candle location"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    distance_from_center: float
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of candle"""
        return (self.x + self.width // 2, self.y + self.height // 2)


class CandleDetector:
    """Detector untuk menemukan candles di game screen"""
    
    def __init__(
        self,
        hsv_lower: Tuple[int, int, int] = (10, 100, 100),
        hsv_upper: Tuple[int, int, int] = (30, 255, 255),
        min_area: int = 100,
        max_area: int = 5000
    ):
        """
        Initialize candle detector
        
        Args:
            hsv_lower: Lower bound HSV untuk orange/yellow candle glow
            hsv_upper: Upper bound HSV untuk orange/yellow candle glow
            min_area: Minimum area untuk valid candle detection
            max_area: Maximum area untuk valid candle detection
        """
        self.hsv_lower = np.array(hsv_lower)
        self.hsv_upper = np.array(hsv_upper)
        self.min_area = min_area
        self.max_area = max_area
        self.sct = mss.mss()
        
    def capture_screen(self, monitor_number: int = 1) -> np.ndarray:
        """
        Capture screenshot dari monitor
        
        Args:
            monitor_number: Monitor index (1 = primary)
            
        Returns:
            numpy array dari screenshot
        """
        try:
            monitor = self.sct.monitors[monitor_number]
            screenshot = self.sct.grab(monitor)
            
            # Convert to numpy array
            img = np.array(screenshot)
            
            # Convert BGRA to BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            return img
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            logger.warning("Returning dummy frame (WSL2/headless environment)")
            
            # Return dummy frame for testing in headless environment
            # In production, you should use remote desktop or run on Windows
            dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            
            # Add warning text to dummy frame
            cv2.putText(
                dummy_frame,
                "NO DISPLAY - Run on Windows or setup X11",
                (400, 540),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 0, 255),
                3
            )
            
            return dummy_frame
        
    def capture_window(self, window_title: str = "Sky") -> Optional[np.ndarray]:
        """
        Capture specific window (advanced, platform-specific)
        
        Args:
            window_title: Title dari game window
            
        Returns:
            numpy array atau None
        """
        # This is platform-specific implementation
        # For now, just capture full screen
        return self.capture_screen()
        
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image untuk candle detection
        
        Args:
            image: Input BGR image
            
        Returns:
            Preprocessed image
        """
        # Convert to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Apply gaussian blur untuk reduce noise
        blurred = cv2.GaussianBlur(hsv, (5, 5), 0)
        
        return blurred
        
    def detect_candles(
        self, 
        image: np.ndarray, 
        debug: bool = False
    ) -> List[CandleLocation]:
        """
        Detect candles di image
        
        Args:
            image: Input BGR image
            debug: Jika True, save intermediate images
            
        Returns:
            List of CandleLocation objects
        """
        height, width = image.shape[:2]
        screen_center = (width // 2, height // 2)
        
        # Preprocess
        hsv = self.preprocess_image(image)
        
        # Create mask untuk candle colors
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Morphological operations untuk clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        candles = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if area < self.min_area or area > self.max_area:
                continue
                
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate confidence based on shape and color
            confidence = self._calculate_confidence(image, x, y, w, h, area)
            
            if confidence < 0.5:  # Threshold
                continue
                
            # Calculate distance from center
            candle_center = (x + w // 2, y + h // 2)
            distance = np.sqrt(
                (candle_center[0] - screen_center[0])**2 + 
                (candle_center[1] - screen_center[1])**2
            )
            
            candle = CandleLocation(
                x=x, y=y, 
                width=w, height=h,
                confidence=confidence,
                distance_from_center=distance
            )
            candles.append(candle)
            
        # Sort by distance (closest first)
        candles.sort(key=lambda c: c.distance_from_center)
        
        logger.info(f"Detected {len(candles)} candles")
        
        if debug:
            self._save_debug_image(image, mask, candles)
            
        return candles
        
    def _calculate_confidence(
        self, 
        image: np.ndarray, 
        x: int, y: int, w: int, h: int, 
        area: float
    ) -> float:
        """
        Calculate confidence score untuk detection
        
        Args:
            image: Original image
            x, y, w, h: Bounding box
            area: Contour area
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        # Extract ROI
        roi = image[y:y+h, x:x+w]
        
        if roi.size == 0:
            return 0.0
            
        # Check color intensity
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mean_value = cv2.mean(hsv_roi)[2]  # V channel
        
        # Candles should be bright
        brightness_score = min(mean_value / 255.0, 1.0)
        
        # Check aspect ratio (candles biasanya vertical)
        aspect_ratio = h / max(w, 1)
        aspect_score = 1.0 if 1.0 <= aspect_ratio <= 3.0 else 0.5
        
        # Combine scores
        confidence = (brightness_score * 0.7) + (aspect_score * 0.3)
        
        return confidence
        
    def get_nearest_candle(
        self, 
        image: np.ndarray
    ) -> Optional[CandleLocation]:
        """
        Get nearest candle dari center screen
        
        Args:
            image: Input BGR image
            
        Returns:
            Nearest CandleLocation atau None
        """
        candles = self.detect_candles(image)
        
        if candles:
            return candles[0]  # Already sorted by distance
        return None
        
    def _save_debug_image(
        self, 
        original: np.ndarray, 
        mask: np.ndarray, 
        candles: List[CandleLocation]
    ):
        """Save debug image dengan annotations"""
        debug_img = original.copy()
        
        # Draw bounding boxes
        for candle in candles:
            cv2.rectangle(
                debug_img,
                (candle.x, candle.y),
                (candle.x + candle.width, candle.y + candle.height),
                (0, 255, 0),
                2
            )
            
            # Draw confidence
            text = f"{candle.confidence:.2f}"
            cv2.putText(
                debug_img,
                text,
                (candle.x, candle.y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )
            
        # Save images
        cv2.imwrite("logs/debug_original.png", original)
        cv2.imwrite("logs/debug_mask.png", mask)
        cv2.imwrite("logs/debug_detections.png", debug_img)
        logger.info("Debug images saved to logs/")
        
    def visualize_detections(
        self, 
        image: np.ndarray, 
        candles: List[CandleLocation]
    ) -> np.ndarray:
        """
        Create visualization dengan detected candles
        
        Args:
            image: Original image
            candles: List of detected candles
            
        Returns:
            Annotated image
        """
        vis_img = image.copy()
        
        # Draw center crosshair
        h, w = vis_img.shape[:2]
        center = (w // 2, h // 2)
        cv2.drawMarker(
            vis_img, center, (255, 0, 0), 
            cv2.MARKER_CROSS, 20, 2
        )
        
        # Draw candles
        for i, candle in enumerate(candles):
            color = (0, 255, 0) if i == 0 else (255, 255, 0)
            
            # Bounding box
            cv2.rectangle(
                vis_img,
                (candle.x, candle.y),
                (candle.x + candle.width, candle.y + candle.height),
                color, 2
            )
            
            # Center point
            cv2.circle(vis_img, candle.center, 5, color, -1)
            
            # Line to center
            cv2.line(vis_img, center, candle.center, color, 1)
            
            # Info text
            text = f"#{i+1} d:{candle.distance_from_center:.0f} c:{candle.confidence:.2f}"
            cv2.putText(
                vis_img, text,
                (candle.x, candle.y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4, color, 1
            )
            
        # Stats
        stats_text = f"Found: {len(candles)} candles"
        cv2.putText(
            vis_img, stats_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (255, 255, 255), 2
        )
        
        return vis_img


class WaxDetector(CandleDetector):
    """Detector untuk wax clusters (area dengan banyak wax particles)"""
    
    def __init__(self):
        # Wax biasanya lebih terang dan sparkly
        super().__init__(
            hsv_lower=(15, 80, 150),
            hsv_upper=(35, 255, 255),
            min_area=50,
            max_area=10000
        )
        
    def detect_wax_clusters(self, image: np.ndarray) -> List[CandleLocation]:
        """Detect wax cluster areas"""
        return self.detect_candles(image)


# Test/Demo function
def demo_candle_detection():
    """Demo candle detection"""
    import time
    
    detector = CandleDetector()
    
    print("Starting candle detection demo...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            # Capture screen
            screen = detector.capture_screen()
            
            # Detect candles
            candles = detector.detect_candles(screen, debug=False)
            
            # Visualize
            vis = detector.visualize_detections(screen, candles)
            
            # Show hasil
            cv2.imshow("Candle Detection", cv2.resize(vis, (960, 540)))
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            time.sleep(0.1)  # 10 FPS
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo_candle_detection()
