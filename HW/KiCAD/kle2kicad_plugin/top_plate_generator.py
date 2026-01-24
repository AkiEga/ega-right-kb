"""
KLE to KiCAD Top Plate Generator
--------------------------------
Generates top plate cutouts, PCB outline, and screw holes for keyboard switches.
"""

import pcbnew
import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class PlateCutout:
    """Represents a single switch cutout on the top plate"""
    center_x: float      # Center X in mm
    center_y: float      # Center Y in mm
    width: float         # Cutout width in mm
    height: float        # Cutout height in mm
    rotation: float      # Rotation in degrees


@dataclass
class ScrewHolePosition:
    """Represents a screw hole position"""
    x: float
    y: float


class TopPlateGenerator:
    """
    Generates top plate cutouts on Edge.Cuts layer.
    
    The top plate has rectangular cutouts for each switch position,
    allowing the switches to snap into place.
    """
    
    # Standard cutout sizes (in mm)
    CHERRY_MX_CUTOUT = (14.0, 14.0)      # Standard Cherry MX
    CHERRY_MX_ALPS = (15.6, 12.8)        # Alps compatible
    KAILH_CHOC = (13.8, 13.8)            # Kailh Choc low profile
    
    # Standard screw hole sizes (in mm)
    M2_HOLE = 2.2
    M2_5_HOLE = 2.7
    M3_HOLE = 3.2
    
    def __init__(self, board: pcbnew.BOARD, settings: Dict):
        """
        Initialize the top plate generator.
        
        Args:
            board: KiCAD board object
            settings: Dictionary containing plate settings
        """
        self.board = board
        self.settings = settings
        self.cutouts_created = 0
        self.outline_created = False
        self.screw_holes_created = 0
        self.bounding_box = None  # Store bounding box for reuse
    
    def generate_cutouts(self, keys: List) -> int:
        """
        Generate switch cutouts on Edge.Cuts layer.
        
        Args:
            keys: List of KeyData objects from KLE parser
            
        Returns:
            Number of cutouts created
        """
        cutout_width = self.settings.get('cutout_width', 14.0)
        cutout_height = self.settings.get('cutout_height', 14.0)
        corner_radius = self.settings.get('cutout_corner_radius', 0.0)
        
        sw_width = self.settings.get('sw_width', 19.05)
        sw_height = self.settings.get('sw_height', 19.05)
        origin_x = self.settings.get('origin_x', 50.0)
        origin_y = self.settings.get('origin_y', 50.0)
        
        for key in keys:
            # Calculate center position (same logic as switch placement)
            center_x = (key.x + key.width / 2) * sw_width + origin_x
            center_y = (key.y + key.height / 2) * sw_height + origin_y
            
            # Apply rotation if needed
            if key.rotation != 0:
                center_x, center_y = self._apply_rotation(
                    center_x, center_y,
                    key.rotation,
                    key.rotation_x * sw_width + origin_x,
                    key.rotation_y * sw_height + origin_y
                )
            
            # Create cutout
            self._create_rectangular_cutout(
                center_x, center_y,
                cutout_width, cutout_height,
                key.rotation,
                corner_radius
            )
            self.cutouts_created += 1
        
        return self.cutouts_created
    
    def generate_outline(self, keys: List, margin: float = 5.0,
                          margin_top: float = None, margin_bottom: float = None,
                          margin_left: float = None, margin_right: float = None) -> bool:
        """
        Generate plate outline on Edge.Cuts layer.
        
        Args:
            keys: List of KeyData objects
            margin: Default margin around the keys in mm (used if specific margins not set)
            margin_top/bottom/left/right: Individual margins (override default)
            
        Returns:
            True if outline was created
        """
        if not keys:
            return False
        
        # Use individual margins if provided, otherwise use default margin
        m_top = margin_top if margin_top is not None else margin
        m_bottom = margin_bottom if margin_bottom is not None else margin
        m_left = margin_left if margin_left is not None else margin
        m_right = margin_right if margin_right is not None else margin
        
        sw_width = self.settings.get('sw_width', 19.05)
        sw_height = self.settings.get('sw_height', 19.05)
        origin_x = self.settings.get('origin_x', 50.0)
        origin_y = self.settings.get('origin_y', 50.0)
        corner_radius = self.settings.get('outline_corner_radius', 3.0)
        
        # Find bounding box
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for key in keys:
            # Calculate key boundaries
            key_left = key.x * sw_width + origin_x
            key_right = (key.x + key.width) * sw_width + origin_x
            key_top = key.y * sw_height + origin_y
            key_bottom = (key.y + key.height) * sw_height + origin_y
            
            # Handle rotation (simplified - uses center point)
            if key.rotation != 0:
                cx = (key_left + key_right) / 2
                cy = (key_top + key_bottom) / 2
                rx, ry = self._apply_rotation(
                    cx, cy,
                    key.rotation,
                    key.rotation_x * sw_width + origin_x,
                    key.rotation_y * sw_height + origin_y
                )
                # Expand bounds for rotated keys (approximate)
                half_diag = math.sqrt((key.width * sw_width)**2 + (key.height * sw_height)**2) / 2
                min_x = min(min_x, rx - half_diag)
                max_x = max(max_x, rx + half_diag)
                min_y = min(min_y, ry - half_diag)
                max_y = max(max_y, ry + half_diag)
            else:
                min_x = min(min_x, key_left)
                max_x = max(max_x, key_right)
                min_y = min(min_y, key_top)
                max_y = max(max_y, key_bottom)
        
        # Add separate margins
        min_x -= m_left
        min_y -= m_top
        max_x += m_right
        max_y += m_bottom
        
        # Store bounding box for screw holes
        self.bounding_box = (min_x, min_y, max_x, max_y)
        
        # Create outline
        self._create_rounded_rectangle_outline(
            min_x, min_y, max_x, max_y, corner_radius
        )
        self.outline_created = True
        
        return True
    
    def _create_rectangular_cutout(self, cx: float, cy: float, 
                                    width: float, height: float,
                                    rotation: float = 0,
                                    corner_radius: float = 0):
        """
        Create a rectangular cutout on Edge.Cuts layer.
        
        Args:
            cx, cy: Center position in mm
            width, height: Cutout dimensions in mm
            rotation: Rotation angle in degrees
            corner_radius: Corner radius in mm (0 for sharp corners)
        """
        half_w = width / 2
        half_h = height / 2
        
        if corner_radius > 0:
            # Rounded rectangle cutout
            self._create_rounded_rectangle(cx, cy, width, height, corner_radius, rotation)
        else:
            # Sharp corner rectangle
            # Calculate corner points
            corners = [
                (-half_w, -half_h),
                (half_w, -half_h),
                (half_w, half_h),
                (-half_w, half_h),
            ]
            
            # Apply rotation to corners
            if rotation != 0:
                rad = math.radians(rotation)
                cos_r = math.cos(rad)
                sin_r = math.sin(rad)
                corners = [
                    (x * cos_r - y * sin_r, x * sin_r + y * cos_r)
                    for x, y in corners
                ]
            
            # Translate to absolute position
            corners = [(x + cx, y + cy) for x, y in corners]
            
            # Draw rectangle on Edge.Cuts
            for i in range(4):
                start = corners[i]
                end = corners[(i + 1) % 4]
                self._draw_line(start[0], start[1], end[0], end[1])
    
    def _create_rounded_rectangle(self, cx: float, cy: float,
                                   width: float, height: float,
                                   radius: float, rotation: float = 0):
        """Create a rounded rectangle cutout"""
        half_w = width / 2
        half_h = height / 2
        r = min(radius, half_w, half_h)  # Clamp radius
        
        # Create segments for rounded rectangle
        segments = []
        
        # Top edge (left to right)
        segments.append(('line', -half_w + r, -half_h, half_w - r, -half_h))
        # Top-right corner
        segments.append(('arc', half_w - r, -half_h + r, r, -90, 0))
        # Right edge
        segments.append(('line', half_w, -half_h + r, half_w, half_h - r))
        # Bottom-right corner
        segments.append(('arc', half_w - r, half_h - r, r, 0, 90))
        # Bottom edge
        segments.append(('line', half_w - r, half_h, -half_w + r, half_h))
        # Bottom-left corner
        segments.append(('arc', -half_w + r, half_h - r, r, 90, 180))
        # Left edge
        segments.append(('line', -half_w, half_h - r, -half_w, -half_h + r))
        # Top-left corner
        segments.append(('arc', -half_w + r, -half_h + r, r, 180, 270))
        
        # Apply rotation and translation
        rad = math.radians(rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        
        def transform(x, y):
            if rotation != 0:
                x, y = x * cos_r - y * sin_r, x * sin_r + y * cos_r
            return x + cx, y + cy
        
        for seg in segments:
            if seg[0] == 'line':
                x1, y1 = transform(seg[1], seg[2])
                x2, y2 = transform(seg[3], seg[4])
                self._draw_line(x1, y1, x2, y2)
            elif seg[0] == 'arc':
                # Arc center, radius, start/end angles
                arc_cx, arc_cy = transform(seg[1], seg[2])
                arc_r = seg[3]
                start_angle = seg[4] + rotation
                end_angle = seg[5] + rotation
                self._draw_arc(arc_cx, arc_cy, arc_r, start_angle, end_angle)
    
    def _create_rounded_rectangle_outline(self, x1: float, y1: float,
                                           x2: float, y2: float,
                                           radius: float):
        """Create a rounded rectangle outline for the plate"""
        width = x2 - x1
        height = y2 - y1
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        self._create_rounded_rectangle(cx, cy, width, height, radius, 0)
    
    def _draw_line(self, x1: float, y1: float, x2: float, y2: float):
        """Draw a line on Edge.Cuts layer"""
        line = pcbnew.PCB_SHAPE(self.board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetStart(pcbnew.VECTOR2I_MM(x1, y1))
        line.SetEnd(pcbnew.VECTOR2I_MM(x2, y2))
        line.SetWidth(pcbnew.FromMM(0.1))  # 0.1mm line width
        self.board.Add(line)
    
    def _draw_arc(self, cx: float, cy: float, radius: float,
                  start_angle: float, end_angle: float):
        """Draw an arc on Edge.Cuts layer"""
        arc = pcbnew.PCB_SHAPE(self.board)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetLayer(pcbnew.Edge_Cuts)
        
        # Calculate start and end points
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)
        
        start_x = cx + radius * math.cos(start_rad)
        start_y = cy + radius * math.sin(start_rad)
        end_x = cx + radius * math.cos(end_rad)
        end_y = cy + radius * math.sin(end_rad)
        
        arc.SetCenter(pcbnew.VECTOR2I_MM(cx, cy))
        arc.SetStart(pcbnew.VECTOR2I_MM(start_x, start_y))
        arc.SetEnd(pcbnew.VECTOR2I_MM(end_x, end_y))
        arc.SetWidth(pcbnew.FromMM(0.1))
        self.board.Add(arc)
    
    def _apply_rotation(self, x: float, y: float, angle: float,
                        center_x: float, center_y: float) -> Tuple[float, float]:
        """Apply rotation around a center point"""
        dx = x - center_x
        dy = y - center_y
        rad = math.radians(angle)
        new_x = dx * math.cos(rad) - dy * math.sin(rad) + center_x
        new_y = dx * math.sin(rad) + dy * math.cos(rad) + center_y
        return new_x, new_y
    
    def calculate_bounding_box(self, keys: List, margin: float = 5.0,
                                 margin_top: float = None, margin_bottom: float = None,
                                 margin_left: float = None, margin_right: float = None) -> Tuple[float, float, float, float]:
        """
        Calculate the bounding box for a set of keys.
        
        Args:
            keys: List of KeyData objects
            margin: Default margin around the keys in mm
            margin_top/bottom/left/right: Individual margins (override default)
            
        Returns:
            Tuple of (min_x, min_y, max_x, max_y)
        """
        if not keys:
            return (0, 0, 0, 0)
        
        # Use individual margins if provided
        m_top = margin_top if margin_top is not None else margin
        m_bottom = margin_bottom if margin_bottom is not None else margin
        m_left = margin_left if margin_left is not None else margin
        m_right = margin_right if margin_right is not None else margin
        
        sw_width = self.settings.get('sw_width', 19.05)
        sw_height = self.settings.get('sw_height', 19.05)
        origin_x = self.settings.get('origin_x', 50.0)
        origin_y = self.settings.get('origin_y', 50.0)
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for key in keys:
            key_left = key.x * sw_width + origin_x
            key_right = (key.x + key.width) * sw_width + origin_x
            key_top = key.y * sw_height + origin_y
            key_bottom = (key.y + key.height) * sw_height + origin_y
            
            if key.rotation != 0:
                cx = (key_left + key_right) / 2
                cy = (key_top + key_bottom) / 2
                rx, ry = self._apply_rotation(
                    cx, cy,
                    key.rotation,
                    key.rotation_x * sw_width + origin_x,
                    key.rotation_y * sw_height + origin_y
                )
                half_diag = math.sqrt((key.width * sw_width)**2 + (key.height * sw_height)**2) / 2
                min_x = min(min_x, rx - half_diag)
                max_x = max(max_x, rx + half_diag)
                min_y = min(min_y, ry - half_diag)
                max_y = max(max_y, ry + half_diag)
            else:
                min_x = min(min_x, key_left)
                max_x = max(max_x, key_right)
                min_y = min(min_y, key_top)
                max_y = max(max_y, key_bottom)
        
        min_x -= m_left
        min_y -= m_top
        max_x += m_right
        max_y += m_bottom
        
        self.bounding_box = (min_x, min_y, max_x, max_y)
        return self.bounding_box
    
    def generate_pcb_outline(self, keys: List, margin: float = 5.0,
                              margin_top: float = None, margin_bottom: float = None,
                              margin_left: float = None, margin_right: float = None) -> bool:
        """
        Generate PCB outline on Edge.Cuts layer (without offset).
        
        Args:
            keys: List of KeyData objects
            margin: Default margin around the keys in mm
            margin_top/bottom/left/right: Individual margins (override default)
            
        Returns:
            True if outline was created
        """
        if not keys:
            return False
        
        corner_radius = self.settings.get('outline_corner_radius', 3.0)
        
        # Calculate bounding box with separate margins
        self.calculate_bounding_box(keys, margin, margin_top, margin_bottom, margin_left, margin_right)
        
        min_x, min_y, max_x, max_y = self.bounding_box
        
        # Create outline (no offset for PCB)
        self._create_rounded_rectangle_outline(min_x, min_y, max_x, max_y, corner_radius)
        
        return True
    
    def generate_screw_holes(self, keys: List, margin: float = 5.0,
                              margin_top: float = None, margin_bottom: float = None,
                              margin_left: float = None, margin_right: float = None,
                              hole_diameter: float = None,
                              corner_holes: bool = True,
                              edge_holes: bool = False,
                              edge_spacing: float = 50.0) -> int:
        """
        Generate screw holes for mounting the plate to PCB.
        
        Args:
            keys: List of KeyData objects
            margin: Default margin around keys in mm
            margin_top/bottom/left/right: Individual margins (override default)
            hole_diameter: Diameter of screw holes in mm (default M2.5 = 2.7mm)
            corner_holes: Whether to place holes near corners
            edge_holes: Whether to place additional holes along edges
            edge_spacing: Spacing between edge holes in mm
            
        Returns:
            Number of screw holes created
        """
        if not keys:
            return 0
        
        if hole_diameter is None:
            hole_diameter = self.settings.get('screw_hole_diameter', self.M2_5_HOLE)
        
        corner_inset = self.settings.get('screw_hole_inset', 5.0)
        
        # Calculate bounding box with separate margins if not already done
        if self.bounding_box is None:
            self.calculate_bounding_box(keys, margin, margin_top, margin_bottom, margin_left, margin_right)
        
        min_x, min_y, max_x, max_y = self.bounding_box
        
        holes: List[ScrewHolePosition] = []
        
        # Corner holes
        if corner_holes:
            holes.append(ScrewHolePosition(min_x + corner_inset, min_y + corner_inset))  # Top-left
            holes.append(ScrewHolePosition(max_x - corner_inset, min_y + corner_inset))  # Top-right
            holes.append(ScrewHolePosition(max_x - corner_inset, max_y - corner_inset))  # Bottom-right
            holes.append(ScrewHolePosition(min_x + corner_inset, max_y - corner_inset))  # Bottom-left
        
        # Edge holes
        if edge_holes:
            width = max_x - min_x - 2 * corner_inset
            height = max_y - min_y - 2 * corner_inset
            
            # Top and bottom edges
            num_horizontal = max(0, int(width / edge_spacing) - 1)
            if num_horizontal > 0:
                spacing = width / (num_horizontal + 1)
                for i in range(1, num_horizontal + 1):
                    x = min_x + corner_inset + i * spacing
                    holes.append(ScrewHolePosition(x, min_y + corner_inset))  # Top
                    holes.append(ScrewHolePosition(x, max_y - corner_inset))  # Bottom
            
            # Left and right edges
            num_vertical = max(0, int(height / edge_spacing) - 1)
            if num_vertical > 0:
                spacing = height / (num_vertical + 1)
                for i in range(1, num_vertical + 1):
                    y = min_y + corner_inset + i * spacing
                    holes.append(ScrewHolePosition(min_x + corner_inset, y))  # Left
                    holes.append(ScrewHolePosition(max_x - corner_inset, y))  # Right
        
        # Draw holes
        for hole in holes:
            self._draw_circle(hole.x, hole.y, hole_diameter / 2)
            self.screw_holes_created += 1
        
        return self.screw_holes_created
    
    def generate_screw_holes_with_offset(self, keys: List, margin: float = 5.0,
                                          offset_x: float = 0, offset_y: float = 0,
                                          hole_diameter: float = None,
                                          corner_holes: bool = True,
                                          edge_holes: bool = False,
                                          edge_spacing: float = 50.0) -> int:
        """
        Generate screw holes at the plate position (with offset).
        
        Args:
            keys: List of KeyData objects
            margin: Margin around keys in mm
            offset_x, offset_y: Offset for plate position
            hole_diameter: Diameter of screw holes in mm
            corner_holes: Whether to place holes near corners
            edge_holes: Whether to place additional holes along edges
            edge_spacing: Spacing between edge holes in mm
            
        Returns:
            Number of screw holes created
        """
        if not keys:
            return 0
        
        if hole_diameter is None:
            hole_diameter = self.settings.get('screw_hole_diameter', self.M2_5_HOLE)
        
        corner_inset = self.settings.get('screw_hole_inset', 5.0)
        
        # Calculate bounding box if not already done
        if self.bounding_box is None:
            self.calculate_bounding_box(keys, margin)
        
        min_x, min_y, max_x, max_y = self.bounding_box
        
        # Apply offset
        min_x += offset_x
        max_x += offset_x
        min_y += offset_y
        max_y += offset_y
        
        holes: List[ScrewHolePosition] = []
        
        if corner_holes:
            holes.append(ScrewHolePosition(min_x + corner_inset, min_y + corner_inset))
            holes.append(ScrewHolePosition(max_x - corner_inset, min_y + corner_inset))
            holes.append(ScrewHolePosition(max_x - corner_inset, max_y - corner_inset))
            holes.append(ScrewHolePosition(min_x + corner_inset, max_y - corner_inset))
        
        if edge_holes:
            width = max_x - min_x - 2 * corner_inset
            height = max_y - min_y - 2 * corner_inset
            
            num_horizontal = max(0, int(width / edge_spacing) - 1)
            if num_horizontal > 0:
                spacing = width / (num_horizontal + 1)
                for i in range(1, num_horizontal + 1):
                    x = min_x + corner_inset + i * spacing
                    holes.append(ScrewHolePosition(x, min_y + corner_inset))
                    holes.append(ScrewHolePosition(x, max_y - corner_inset))
            
            num_vertical = max(0, int(height / edge_spacing) - 1)
            if num_vertical > 0:
                spacing = height / (num_vertical + 1)
                for i in range(1, num_vertical + 1):
                    y = min_y + corner_inset + i * spacing
                    holes.append(ScrewHolePosition(min_x + corner_inset, y))
                    holes.append(ScrewHolePosition(max_x - corner_inset, y))
        
        count = 0
        for hole in holes:
            self._draw_circle(hole.x, hole.y, hole_diameter / 2)
            count += 1
        
        self.screw_holes_created += count
        return count
    
    def _draw_circle(self, cx: float, cy: float, radius: float):
        """Draw a circle on Edge.Cuts layer"""
        circle = pcbnew.PCB_SHAPE(self.board)
        circle.SetShape(pcbnew.SHAPE_T_CIRCLE)
        circle.SetLayer(pcbnew.Edge_Cuts)
        circle.SetCenter(pcbnew.VECTOR2I_MM(cx, cy))
        # Set end point on the circle circumference to define radius
        circle.SetEnd(pcbnew.VECTOR2I_MM(cx + radius, cy))
        circle.SetWidth(pcbnew.FromMM(0.1))
        self.board.Add(circle)
    
    def generate_vcut_line(self, keys: List, margin_left: float = 5.0, margin_right: float = 5.0,
                           pcb_margin_bottom: float = 5.0, plate_margin_top: float = 5.0,
                           plate_offset_y: float = 150.0) -> bool:
        """
        Generate V-cut line between PCB and top plate.
        
        The V-cut line is placed at the midpoint between PCB bottom and plate top.
        
        Args:
            keys: List of KeyData objects
            margin_left: Left margin of the outline
            margin_right: Right margin of the outline
            pcb_margin_bottom: Bottom margin of PCB outline
            plate_margin_top: Top margin of plate outline
            plate_offset_y: Y offset of plate from PCB
            
        Returns:
            True if V-cut line was created
        """
        if not keys:
            return False
        
        sw_width = self.settings.get('sw_width', 19.05)
        sw_height = self.settings.get('sw_height', 19.05)
        origin_x = self.settings.get('origin_x', 50.0)
        origin_y = self.settings.get('origin_y', 50.0)
        
        # Find horizontal extent of keys
        min_x = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for key in keys:
            key_left = key.x * sw_width + origin_x
            key_right = (key.x + key.width) * sw_width + origin_x
            key_bottom = (key.y + key.height) * sw_height + origin_y
            
            if key.rotation != 0:
                cx = (key_left + key_right) / 2
                cy = key_bottom - (key.height * sw_height) / 2
                rx, ry = self._apply_rotation(
                    cx, cy,
                    key.rotation,
                    key.rotation_x * sw_width + origin_x,
                    key.rotation_y * sw_height + origin_y
                )
                half_diag = math.sqrt((key.width * sw_width)**2 + (key.height * sw_height)**2) / 2
                min_x = min(min_x, rx - half_diag)
                max_x = max(max_x, rx + half_diag)
                max_y = max(max_y, ry + half_diag)
            else:
                min_x = min(min_x, key_left)
                max_x = max(max_x, key_right)
                max_y = max(max_y, key_bottom)
        
        # Calculate V-cut line position
        # PCB bottom edge
        pcb_bottom = max_y + pcb_margin_bottom
        # Plate top edge (with offset)
        plate_top = origin_y + plate_offset_y - plate_margin_top
        
        # V-cut at the midpoint (shared edge)
        vcut_y = pcb_bottom  # V-cut at PCB bottom = Plate top
        
        # Line extends from left margin to right margin
        line_left = min_x - margin_left
        line_right = max_x + margin_right
        
        # Draw V-cut line on Edge.Cuts layer
        self._draw_line(line_left, vcut_y, line_right, vcut_y)
        
        return True
    
    def clear_edge_cuts(self):
        """Remove all items from Edge.Cuts layer"""
        to_remove = []
        for item in self.board.GetDrawings():
            if item.GetLayer() == pcbnew.Edge_Cuts:
                to_remove.append(item)
        
        for item in to_remove:
            self.board.Remove(item)
        
        return len(to_remove)
