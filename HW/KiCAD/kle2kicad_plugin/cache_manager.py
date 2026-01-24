"""
KLE to KiCAD Cache Manager
--------------------------
Manages caching of settings and execution results.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ExecutionResult:
    """Represents a single execution result"""
    timestamp: str
    kle_file: str
    pcb_file: str
    settings: Dict
    switches_placed: int
    diodes_placed: int
    warnings: int
    warning_messages: List[str]


class CacheManager:
    """
    Manages caching of plugin settings and execution history.
    Cache is stored as JSON in the plugin directory.
    """
    
    CACHE_FILENAME = "kle2kicad_cache.json"
    MAX_HISTORY_ENTRIES = 10
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cache file. 
                       Defaults to plugin directory.
        """
        if cache_dir is None:
            cache_dir = os.path.dirname(__file__)
        
        self.cache_path = os.path.join(cache_dir, self.CACHE_FILENAME)
        self._cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Return default cache structure
        return {
            'version': '1.0',
            'last_settings': None,
            'last_kle_file': None,
            'history': []
        }
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save cache: {e}")
    
    def get_last_settings(self) -> Optional[Dict]:
        """
        Get the last used settings.
        
        Returns:
            Dictionary of settings or None if no cached settings exist.
        """
        return self._cache.get('last_settings')
    
    def save_settings(self, settings: Dict):
        """
        Save settings to cache.
        
        Args:
            settings: Dictionary of settings to save.
        """
        self._cache['last_settings'] = settings.copy()
        self._save_cache()
    
    def get_last_kle_file(self) -> Optional[str]:
        """
        Get the path to the last used KLE file.
        
        Returns:
            File path or None if no cached path exists.
        """
        path = self._cache.get('last_kle_file')
        # Only return if file still exists
        if path and os.path.exists(path):
            return path
        return None
    
    def save_kle_file_path(self, path: str):
        """
        Save the KLE file path to cache.
        
        Args:
            path: Path to the KLE JSON file.
        """
        self._cache['last_kle_file'] = path
        self._save_cache()
    
    def add_execution_result(self, kle_file: str, pcb_file: str, 
                             settings: Dict, result: Dict):
        """
        Add an execution result to history.
        
        Args:
            kle_file: Path to the KLE JSON file used.
            pcb_file: Path to the KiCAD PCB file.
            settings: Settings used for execution.
            result: Result dictionary from KLE2KiCADCore.execute().
        """
        entry = ExecutionResult(
            timestamp=datetime.now().isoformat(),
            kle_file=kle_file,
            pcb_file=pcb_file,
            settings=settings.copy(),
            switches_placed=result.get('switches_placed', 0),
            diodes_placed=result.get('diodes_placed', 0),
            warnings=result.get('warnings', 0),
            warning_messages=result.get('warning_messages', [])
        )
        
        # Add to history
        history = self._cache.get('history', [])
        history.insert(0, asdict(entry))
        
        # Trim history to max entries
        self._cache['history'] = history[:self.MAX_HISTORY_ENTRIES]
        
        # Also update last settings and file
        self._cache['last_settings'] = settings.copy()
        self._cache['last_kle_file'] = kle_file
        
        self._save_cache()
    
    def get_history(self) -> List[Dict]:
        """
        Get execution history.
        
        Returns:
            List of execution result dictionaries, newest first.
        """
        return self._cache.get('history', [])
    
    def get_last_execution(self) -> Optional[Dict]:
        """
        Get the most recent execution result.
        
        Returns:
            Execution result dictionary or None.
        """
        history = self.get_history()
        return history[0] if history else None
    
    def clear_history(self):
        """Clear execution history"""
        self._cache['history'] = []
        self._save_cache()
    
    def clear_all(self):
        """Clear all cached data"""
        self._cache = {
            'version': '1.0',
            'last_settings': None,
            'last_kle_file': None,
            'history': []
        }
        self._save_cache()
    
    def get_default_settings(self) -> Dict:
        """
        Get default settings, using cached values if available.
        
        Returns:
            Dictionary of settings with defaults filled in.
        """
        defaults = {
            # Basic settings
            'origin_x': 50.0,
            'origin_y': 50.0,
            'sw_width': 19.05,
            'sw_height': 19.05,
            # Diode settings
            'place_diodes': True,
            'diode_offset_x': 0.0,
            'diode_offset_y': 5.08,
            'diode_rotation': 90.0,
            # Top plate settings
            'generate_plate': False,
            'plate_offset_x': 0.0,
            'plate_offset_y': 150.0,
            'generate_vcut': True,
            'cutout_width': 14.0,
            'cutout_height': 14.0,
            'cutout_corner_radius': 0.0,
            'generate_outline': False,
            'margin_top': 5.0,
            'margin_bottom': 5.0,
            'margin_left': 5.0,
            'margin_right': 5.0,
            'outline_corner_radius': 3.0,
            'clear_edge_cuts': False,
            # PCB outline settings
            'generate_pcb_outline': False,
            # Screw hole settings
            'generate_screw_holes': False,
            'screw_hole_diameter': 2.7,
            'screw_hole_inset': 5.0,
            'screw_edge_spacing': 50.0,
            'screw_corner_holes': True,
            'screw_edge_holes': False,
        }
        
        # Merge with cached settings (cached values override defaults)
        cached = self.get_last_settings()
        if cached:
            for key in defaults:
                if key in cached:
                    defaults[key] = cached[key]
        
        return defaults
