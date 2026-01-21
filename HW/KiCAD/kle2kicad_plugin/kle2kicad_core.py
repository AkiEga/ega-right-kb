"""
KLE to KiCAD Core Logic
-----------------------
Core functionality for parsing KLE JSON and placing footprints.
"""

import pcbnew
import json
import re
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class KeyData:
    """Represents a single key from KLE JSON"""
    ref: str                    # Reference designator (e.g., "SW00")
    x: float = 0.0              # X position in key units
    y: float = 0.0              # Y position in key units
    width: float = 1.0          # Key width in key units
    height: float = 1.0         # Key height in key units
    rotation: float = 0.0       # Rotation angle in degrees
    rotation_x: float = 0.0     # Rotation center X
    rotation_y: float = 0.0     # Rotation center Y
    # ISO Enter support (stepped keys)
    width2: float = 0.0         # Secondary width
    height2: float = 0.0        # Secondary height
    x2: float = 0.0             # Secondary x offset
    y2: float = 0.0             # Secondary y offset


@dataclass
class LayoutData:
    """Represents a group of keys with common offset"""
    offset_x: float
    offset_y: float
    refs: List[str] = field(default_factory=list)
    keys: List[KeyData] = field(default_factory=list)


class KLEParser:
    """
    Parser for keyboard-layout-editor.com JSON format.
    
    KLE JSON format reference:
    - Each row is an array
    - Objects in the array are property modifiers for subsequent keys
    - Strings are key labels (we use them as references like "SW00")
    """
    
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.keys: List[KeyData] = []
        
    def parse(self) -> List[KeyData]:
        """
        Parse the KLE JSON file and return a list of KeyData objects.
        """
        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Current position tracking
        current_x = 0.0
        current_y = 0.0
        
        # Current key properties (reset for each key)
        current_props = self._default_key_props()
        
        # Rotation state (persists across keys until changed)
        rotation = 0.0
        rotation_x = 0.0
        rotation_y = 0.0
        
        for row in data:
            if not isinstance(row, list):
                continue
                
            # Reset X at the start of each row
            current_x = 0.0
            
            for item in row:
                if isinstance(item, dict):
                    # Property modifier - update current properties
                    current_props = self._apply_properties(current_props, item)
                    
                    # Handle position offsets
                    if 'x' in item:
                        current_x += item['x']
                    if 'y' in item:
                        current_y += item['y']
                    
                    # Handle rotation (persists)
                    if 'r' in item:
                        rotation = item['r']
                    if 'rx' in item:
                        rotation_x = item['rx']
                        current_x = rotation_x  # Reset X to rotation center
                    if 'ry' in item:
                        rotation_y = item['ry']
                        current_y = rotation_y  # Reset Y to rotation center
                        
                elif isinstance(item, str):
                    # This is a key - extract reference
                    ref = self._extract_ref(item)
                    
                    if ref:
                        key = KeyData(
                            ref=ref,
                            x=current_x,
                            y=current_y,
                            width=current_props['w'],
                            height=current_props['h'],
                            rotation=rotation,
                            rotation_x=rotation_x,
                            rotation_y=rotation_y,
                            width2=current_props['w2'],
                            height2=current_props['h2'],
                            x2=current_props['x2'],
                            y2=current_props['y2'],
                        )
                        self.keys.append(key)
                    
                    # Move X position for next key
                    current_x += current_props['w']
                    
                    # Reset per-key properties
                    current_props = self._default_key_props()
            
            # Move to next row
            current_y += 1.0
        
        return self.keys
    
    def _default_key_props(self) -> Dict:
        """Return default key properties"""
        return {
            'w': 1.0,   # width
            'h': 1.0,   # height
            'w2': 0.0,  # secondary width (for ISO Enter)
            'h2': 0.0,  # secondary height
            'x2': 0.0,  # secondary x offset
            'y2': 0.0,  # secondary y offset
        }
    
    def _apply_properties(self, props: Dict, item: Dict) -> Dict:
        """Apply property modifiers from JSON object"""
        new_props = props.copy()
        
        if 'w' in item:
            new_props['w'] = item['w']
        if 'h' in item:
            new_props['h'] = item['h']
        if 'w2' in item:
            new_props['w2'] = item['w2']
        if 'h2' in item:
            new_props['h2'] = item['h2']
        if 'x2' in item:
            new_props['x2'] = item['x2']
        if 'y2' in item:
            new_props['y2'] = item['y2']
            
        return new_props
    
    def _extract_ref(self, label: str) -> Optional[str]:
        """
        Extract switch reference from key label.
        Supports formats like "SW00", "SW0", "SW123"
        """
        match = re.search(r'SW\d{1,3}', label)
        return match.group() if match else None


class KLE2KiCADCore:
    """
    Core class for placing footprints based on KLE layout.
    """
    
    def __init__(self, board: pcbnew.BOARD, kle_path: str, settings: Dict):
        self.board = board
        self.kle_path = kle_path
        self.settings = settings
        
        # Statistics
        self.switches_placed = 0
        self.diodes_placed = 0
        self.warnings: List[str] = []
    
    def execute(self) -> Dict:
        """
        Execute the layout operation.
        Returns a dictionary with results.
        """
        # Parse the KLE JSON
        parser = KLEParser(self.kle_path)
        keys = parser.parse()
        
        # Place footprints
        for key in keys:
            self._place_switch(key)
            
            if self.settings['place_diodes']:
                self._place_diode(key)
        
        return {
            'switches_placed': self.switches_placed,
            'diodes_placed': self.diodes_placed,
            'warnings': len(self.warnings),
            'warning_messages': self.warnings,
        }
    
    def _place_switch(self, key: KeyData):
        """Place a switch footprint"""
        footprint = self.board.FindFootprintByReference(key.ref)
        
        if footprint is None:
            self.warnings.append(f"Switch {key.ref} not found on board")
            return
        
        # Calculate position in mm
        x_mm, y_mm = self._key_to_mm(key.x, key.y, key.width, key.height)
        
        # Apply rotation if needed
        if key.rotation != 0:
            x_mm, y_mm = self._apply_rotation(
                x_mm, y_mm,
                key.rotation,
                key.rotation_x * self.settings['sw_width'],
                key.rotation_y * self.settings['sw_height']
            )
        
        # Add origin offset
        x_mm += self.settings['origin_x']
        y_mm += self.settings['origin_y']
        
        # Set position
        footprint.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
        
        # Set rotation
        footprint.SetOrientationDegrees(key.rotation)
        
        self.switches_placed += 1
    
    def _place_diode(self, key: KeyData):
        """Place a diode footprint relative to its switch"""
        # Convert SW reference to D reference (SW00 -> D00)
        diode_ref = key.ref.replace("SW", "D")
        footprint = self.board.FindFootprintByReference(diode_ref)
        
        if footprint is None:
            self.warnings.append(f"Diode {diode_ref} not found on board")
            return
        
        # Calculate base switch position
        x_mm, y_mm = self._key_to_mm(key.x, key.y, key.width, key.height)
        
        # Apply rotation for switch position first
        if key.rotation != 0:
            x_mm, y_mm = self._apply_rotation(
                x_mm, y_mm,
                key.rotation,
                key.rotation_x * self.settings['sw_width'],
                key.rotation_y * self.settings['sw_height']
            )
        
        # Add diode offset (also rotated if switch is rotated)
        diode_offset_x = self.settings['diode_offset_x']
        diode_offset_y = self.settings['diode_offset_y']
        
        if key.rotation != 0:
            # Rotate the offset vector
            import math
            rad = math.radians(key.rotation)
            rotated_x = diode_offset_x * math.cos(rad) - diode_offset_y * math.sin(rad)
            rotated_y = diode_offset_x * math.sin(rad) + diode_offset_y * math.cos(rad)
            diode_offset_x = rotated_x
            diode_offset_y = rotated_y
        
        x_mm += diode_offset_x
        y_mm += diode_offset_y
        
        # Add origin offset
        x_mm += self.settings['origin_x']
        y_mm += self.settings['origin_y']
        
        # Set position
        footprint.SetPosition(pcbnew.VECTOR2I_MM(x_mm, y_mm))
        
        # Set rotation (switch rotation + diode rotation setting)
        total_rotation = key.rotation + self.settings['diode_rotation']
        footprint.SetOrientationDegrees(total_rotation)
        
        self.diodes_placed += 1
    
    def _key_to_mm(self, x: float, y: float, width: float, height: float) -> Tuple[float, float]:
        """
        Convert key position (in key units) to mm.
        Key position is at top-left, we need center position.
        """
        sw_width = self.settings['sw_width']
        sw_height = self.settings['sw_height']
        
        # Calculate center position
        center_x = (x + width / 2) * sw_width
        center_y = (y + height / 2) * sw_height
        
        return center_x, center_y
    
    def _apply_rotation(self, x: float, y: float, angle: float, 
                        center_x: float, center_y: float) -> Tuple[float, float]:
        """
        Apply rotation around a center point.
        """
        import math
        
        # Add origin offset to center for rotation calculation
        center_x += self.settings['origin_x']
        center_y += self.settings['origin_y']
        
        # Translate to rotation center
        dx = x - center_x
        dy = y - center_y
        
        # Rotate
        rad = math.radians(angle)
        new_x = dx * math.cos(rad) - dy * math.sin(rad)
        new_y = dx * math.sin(rad) + dy * math.cos(rad)
        
        # Translate back (but don't add origin yet, that's done in caller)
        return new_x + center_x - self.settings['origin_x'], new_y + center_y - self.settings['origin_y']
