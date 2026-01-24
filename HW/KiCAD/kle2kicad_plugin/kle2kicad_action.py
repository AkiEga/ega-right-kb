"""
KLE to KiCAD Action Plugin
--------------------------
Action Plugin class for the KLE to KiCAD Layout plugin.
This integrates with KiCAD's Plugin menu (Tools -> External Plugins).
"""

import pcbnew
import os
import wx
import wx.lib.scrolledpanel as scrolled

class KLE2KiCADAction(pcbnew.ActionPlugin):
    """
    KiCAD Action Plugin for importing keyboard layouts from keyboard-layout-editor.com
    """
    
    def defaults(self):
        """
        Define plugin metadata and settings.
        Called by KiCAD when registering the plugin.
        """
        self.name = "KLE to KiCAD Layout"
        self.category = "Keyboard Layout"
        self.description = "Import keyboard layout from keyboard-layout-editor.com JSON and auto-place switch/diode footprints"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), 'icon_dark.png')
    
    def Run(self):
        """
        Entry point when user activates the plugin.
        Shows a dialog and performs the layout operation.
        """
        from .kle2kicad_core import KLE2KiCADCore
        from .cache_manager import CacheManager
        
        # Initialize cache manager
        cache = CacheManager()
        
        # Get the current board
        board = pcbnew.GetBoard()
        if board is None:
            wx.MessageBox("No board is currently open!", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Determine default directory for file dialog
        # Priority: 1. Last used KLE file directory, 2. Board file directory
        default_dir = ""
        last_kle_file = cache.get_last_kle_file()
        if last_kle_file:
            default_dir = os.path.dirname(last_kle_file)
        elif board.GetFileName():
            default_dir = os.path.dirname(board.GetFileName())
        
        # Show file selection dialog
        dialog = wx.FileDialog(
            None,
            message="Select KLE JSON file",
            defaultDir=default_dir,
            defaultFile="",
            wildcard="KLE JSON files (*.json)|*.json|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return
        
        kle_path = dialog.GetPath()
        dialog.Destroy()
        
        # Show settings dialog with cached settings
        settings_dialog = KLE2KiCADSettingsDialog(None, kle_path, cache)
        if settings_dialog.ShowModal() != wx.ID_OK:
            settings_dialog.Destroy()
            return
        
        settings = settings_dialog.get_settings()
        settings_dialog.Destroy()
        
        # Execute the layout
        try:
            core = KLE2KiCADCore(board, kle_path, settings)
            result = core.execute()
            
            # Generate top plate if enabled
            plate_result = {'cutouts_created': 0, 'outline_created': False}
            pcb_result = {'outline_created': False}
            screw_result = {'pcb_holes': 0, 'plate_holes': 0}
            
            # Parse KLE to get key positions (needed for plate/outline/screws)
            from .top_plate_generator import TopPlateGenerator
            from .kle2kicad_core import KLEParser
            
            parser = KLEParser(kle_path)
            keys = parser.parse()
            
            # Create base settings for PCB outline and screw holes
            base_settings = settings.copy()
            base_settings['screw_hole_diameter'] = settings.get('screw_hole_diameter', 2.7)
            base_settings['screw_hole_inset'] = settings.get('screw_hole_inset', 5.0)
            
            # Optionally clear existing Edge.Cuts
            if settings.get('clear_edge_cuts', False):
                pcb_gen = TopPlateGenerator(board, base_settings)
                pcb_gen.clear_edge_cuts()
            
            # Generate PCB outline if enabled
            if settings.get('generate_pcb_outline', False):
                pcb_gen = TopPlateGenerator(board, base_settings)
                pcb_result['outline_created'] = pcb_gen.generate_pcb_outline(
                    keys,
                    margin_top=settings.get('margin_top', 5.0),
                    margin_bottom=settings.get('margin_bottom', 5.0),
                    margin_left=settings.get('margin_left', 5.0),
                    margin_right=settings.get('margin_right', 5.0)
                )
                
                # Generate screw holes on PCB if enabled
                if settings.get('generate_screw_holes', False):
                    screw_result['pcb_holes'] = pcb_gen.generate_screw_holes(
                        keys,
                        margin_top=settings.get('margin_top', 5.0),
                        margin_bottom=settings.get('margin_bottom', 5.0),
                        margin_left=settings.get('margin_left', 5.0),
                        margin_right=settings.get('margin_right', 5.0),
                        hole_diameter=settings.get('screw_hole_diameter', 2.7),
                        corner_holes=settings.get('screw_corner_holes', True),
                        edge_holes=settings.get('screw_edge_holes', False),
                        edge_spacing=settings.get('screw_edge_spacing', 50.0)
                    )
            
            # Generate top plate if enabled
            if settings.get('generate_plate', False):
                # Create plate settings with offset applied
                plate_settings = settings.copy()
                plate_settings['origin_x'] = settings['origin_x'] + settings.get('plate_offset_x', 350.0)
                plate_settings['origin_y'] = settings['origin_y'] + settings.get('plate_offset_y', 0.0)
                plate_settings['screw_hole_diameter'] = settings.get('screw_hole_diameter', 2.7)
                plate_settings['screw_hole_inset'] = settings.get('screw_hole_inset', 5.0)
                
                # Generate plate on the same board with offset
                plate_gen = TopPlateGenerator(board, plate_settings)
                
                plate_result['cutouts_created'] = plate_gen.generate_cutouts(keys)
                
                if settings.get('generate_outline', False):
                    plate_result['outline_created'] = plate_gen.generate_outline(
                        keys,
                        margin_top=settings.get('margin_top', 5.0),
                        margin_bottom=settings.get('margin_bottom', 5.0),
                        margin_left=settings.get('margin_left', 5.0),
                        margin_right=settings.get('margin_right', 5.0)
                    )
                
                # Generate screw holes on plate if enabled
                if settings.get('generate_screw_holes', False):
                    screw_result['plate_holes'] = plate_gen.generate_screw_holes(
                        keys,
                        margin_top=settings.get('margin_top', 5.0),
                        margin_bottom=settings.get('margin_bottom', 5.0),
                        margin_left=settings.get('margin_left', 5.0),
                        margin_right=settings.get('margin_right', 5.0),
                        hole_diameter=settings.get('screw_hole_diameter', 2.7),
                        corner_holes=settings.get('screw_corner_holes', True),
                        edge_holes=settings.get('screw_edge_holes', False),
                        edge_spacing=settings.get('screw_edge_spacing', 50.0)
                    )
            
            # Generate V-cut line if enabled
            vcut_created = False
            if settings.get('generate_plate', False) and settings.get('generate_vcut', False):
                vcut_gen = TopPlateGenerator(board, base_settings)
                vcut_created = vcut_gen.generate_vcut_line(
                    keys,
                    margin_left=settings.get('margin_left', 5.0),
                    margin_right=settings.get('margin_right', 5.0),
                    pcb_margin_bottom=settings.get('margin_bottom', 5.0),
                    plate_margin_top=settings.get('margin_top', 5.0),
                    plate_offset_y=settings.get('plate_offset_y', 150.0)
                )
            
            # Save to cache
            pcb_path = board.GetFileName() if board.GetFileName() else "Unsaved"
            cache.add_execution_result(kle_path, pcb_path, settings, result)
            
            # Refresh the display
            pcbnew.Refresh()
            
            # Build result message
            msg = "Layout completed!\n\n"
            msg += f"Switches placed: {result['switches_placed']}\n"
            msg += f"Diodes placed: {result['diodes_placed']}\n"
            
            if settings.get('generate_pcb_outline', False):
                msg += "\nPCB Outline:\n"
                msg += f"  Outline created: {'Yes' if pcb_result['outline_created'] else 'No'}\n"
                if settings.get('generate_screw_holes', False):
                    msg += f"  Screw holes: {screw_result['pcb_holes']}\n"
            
            if settings.get('generate_plate', False):
                msg += f"\nTop Plate (offset X:{settings.get('plate_offset_x', 0.0)}mm, Y:{settings.get('plate_offset_y', 150.0)}mm):\n"
                msg += f"  Cutouts created: {plate_result['cutouts_created']}\n"
                msg += f"  Outline created: {'Yes' if plate_result['outline_created'] else 'No'}\n"
                if settings.get('generate_screw_holes', False):
                    msg += f"  Screw holes: {screw_result['plate_holes']}\n"
                if settings.get('generate_vcut', False):
                    msg += f"  V-cut line: {'Yes' if vcut_created else 'No'}\n"
            
            msg += f"\nWarnings: {result['warnings']}\n"
            msg += "\nSettings saved to cache."
            
            # Show result
            wx.MessageBox(msg, "KLE to KiCAD", wx.OK | wx.ICON_INFORMATION)
            
        except Exception as e:
            wx.MessageBox(f"Error during layout:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)


class KLE2KiCADSettingsDialog(wx.Dialog):
    """
    Settings dialog for KLE to KiCAD plugin.
    Allows user to configure layout parameters.
    """
    
    def __init__(self, parent, kle_path, cache_manager=None):
        super().__init__(parent, title="KLE to KiCAD Settings", size=(1200, 1200),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.kle_path = kle_path
        self.cache_manager = cache_manager
        self._init_ui()
        self._load_cached_settings()
        self.SetMinSize((1000, 1000))
        self.Centre()
    
    def _load_cached_settings(self):
        """Load cached settings into the UI controls"""
        if self.cache_manager is None:
            return
        
        settings = self.cache_manager.get_default_settings()
        
        self.origin_x.SetValue(settings['origin_x'])
        self.origin_y.SetValue(settings['origin_y'])
        self.sw_width.SetValue(settings['sw_width'])
        self.sw_height.SetValue(settings['sw_height'])
        self.place_diodes.SetValue(settings['place_diodes'])
        self.diode_offset_x.SetValue(settings['diode_offset_x'])
        self.diode_offset_y.SetValue(settings['diode_offset_y'])
        self.diode_rotation.SetValue(settings['diode_rotation'])
        
        # Top plate settings
        self.generate_plate.SetValue(settings.get('generate_plate', False))
        self.plate_offset_x.SetValue(settings.get('plate_offset_x', 350.0))
        self.plate_offset_y.SetValue(settings.get('plate_offset_y', 150.0))
        self.generate_vcut.SetValue(settings.get('generate_vcut', True))
        self.cutout_width.SetValue(settings.get('cutout_width', 14.0))
        self.cutout_height.SetValue(settings.get('cutout_height', 14.0))
        self.cutout_corner_radius.SetValue(settings.get('cutout_corner_radius', 0.0))
        self.generate_outline.SetValue(settings.get('generate_outline', False))
        self.margin_top.SetValue(settings.get('margin_top', 5.0))
        self.margin_bottom.SetValue(settings.get('margin_bottom', 5.0))
        self.margin_left.SetValue(settings.get('margin_left', 5.0))
        self.margin_right.SetValue(settings.get('margin_right', 5.0))
        self.outline_corner_radius.SetValue(settings.get('outline_corner_radius', 3.0))
        self.clear_edge_cuts.SetValue(settings.get('clear_edge_cuts', False))
        
        # PCB outline settings
        self.generate_pcb_outline.SetValue(settings.get('generate_pcb_outline', False))
        
        # Screw hole settings
        self.generate_screw_holes.SetValue(settings.get('generate_screw_holes', False))
        self.screw_hole_diameter.SetValue(settings.get('screw_hole_diameter', 2.7))
        self.screw_hole_inset.SetValue(settings.get('screw_hole_inset', 5.0))
        self.screw_edge_spacing.SetValue(settings.get('screw_edge_spacing', 50.0))
        self.screw_corner_holes.SetValue(settings.get('screw_corner_holes', True))
        self.screw_edge_holes.SetValue(settings.get('screw_edge_holes', False))
        
        # Update enabled states
        self._on_generate_plate_changed(None)
        self._on_generate_screw_holes_changed(None)
    
    def _init_ui(self):
        """Initialize the dialog UI with two-column layout"""
        # Use ScrolledPanel for scrollbar support
        panel = scrolled.ScrolledPanel(self)
        panel.SetupScrolling(scroll_x=True, scroll_y=True, rate_x=20, rate_y=20)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # File info (top, full width)
        file_box = wx.StaticBox(panel, label="Selected File")
        file_sizer = wx.StaticBoxSizer(file_box, wx.HORIZONTAL)
        file_label = wx.StaticText(panel, label=os.path.basename(self.kle_path))
        file_sizer.Add(file_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        # Last execution info (inline if available)
        if self.cache_manager:
            last_exec = self.cache_manager.get_last_execution()
            if last_exec:
                timestamp = last_exec.get('timestamp', 'Unknown')[:19].replace('T', ' ')
                switches = last_exec.get('switches_placed', 0)
                diodes = last_exec.get('diodes_placed', 0)
                history_text = f"  |  Last: {timestamp} ({switches} SW, {diodes} D)"
                history_label = wx.StaticText(panel, label=history_text)
                history_label.SetForegroundColour(wx.Colour(100, 100, 100))
                file_sizer.Add(history_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Two-column layout
        columns_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # ===== LEFT COLUMN: Basic Settings =====
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Origin settings
        origin_box = wx.StaticBox(panel, label="Origin (mm)")
        origin_sizer = wx.StaticBoxSizer(origin_box, wx.VERTICAL)
        origin_grid = wx.FlexGridSizer(2, 2, 3, 5)
        origin_grid.Add(wx.StaticText(panel, label="X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.origin_x = wx.SpinCtrlDouble(panel, value="50", min=0, max=500, inc=1, size=(160, -1))
        origin_grid.Add(self.origin_x, 0)
        origin_grid.Add(wx.StaticText(panel, label="Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.origin_y = wx.SpinCtrlDouble(panel, value="50", min=0, max=500, inc=1, size=(160, -1))
        origin_grid.Add(self.origin_y, 0)
        origin_sizer.Add(origin_grid, 0, wx.ALL, 3)
        left_sizer.Add(origin_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        # Switch settings
        switch_box = wx.StaticBox(panel, label="Switch Pitch (mm)")
        switch_sizer = wx.StaticBoxSizer(switch_box, wx.VERTICAL)
        switch_grid = wx.FlexGridSizer(2, 2, 3, 5)
        switch_grid.Add(wx.StaticText(panel, label="W:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sw_width = wx.SpinCtrlDouble(panel, value="19.05", min=10, max=30, inc=0.01, size=(160, -1))
        switch_grid.Add(self.sw_width, 0)
        switch_grid.Add(wx.StaticText(panel, label="H:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sw_height = wx.SpinCtrlDouble(panel, value="19.05", min=10, max=30, inc=0.01, size=(160, -1))
        switch_grid.Add(self.sw_height, 0)
        switch_sizer.Add(switch_grid, 0, wx.ALL, 3)
        left_sizer.Add(switch_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        # Diode settings
        diode_box = wx.StaticBox(panel, label="Diode")
        diode_sizer = wx.StaticBoxSizer(diode_box, wx.VERTICAL)
        self.place_diodes = wx.CheckBox(panel, label="Auto-place (D)")
        self.place_diodes.SetValue(True)
        diode_sizer.Add(self.place_diodes, 0, wx.ALL, 3)
        diode_grid = wx.FlexGridSizer(3, 2, 3, 5)
        diode_grid.Add(wx.StaticText(panel, label="Offset X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_offset_x = wx.SpinCtrlDouble(panel, value="0", min=-20, max=20, inc=0.1, size=(160, -1))
        diode_grid.Add(self.diode_offset_x, 0)
        diode_grid.Add(wx.StaticText(panel, label="Offset Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_offset_y = wx.SpinCtrlDouble(panel, value="5.08", min=-20, max=20, inc=0.1, size=(160, -1))
        diode_grid.Add(self.diode_offset_y, 0)
        diode_grid.Add(wx.StaticText(panel, label="Rotation:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_rotation = wx.SpinCtrlDouble(panel, value="90", min=0, max=360, inc=1, size=(160, -1))
        diode_grid.Add(self.diode_rotation, 0)
        diode_sizer.Add(diode_grid, 0, wx.ALL, 3)
        left_sizer.Add(diode_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        # PCB Outline settings
        pcb_box = wx.StaticBox(panel, label="PCB Outline")
        pcb_sizer = wx.StaticBoxSizer(pcb_box, wx.VERTICAL)
        self.generate_pcb_outline = wx.CheckBox(panel, label="Generate outline")
        self.generate_pcb_outline.SetValue(False)
        pcb_sizer.Add(self.generate_pcb_outline, 0, wx.ALL, 3)
        self.clear_edge_cuts = wx.CheckBox(panel, label="Clear Edge.Cuts first")
        self.clear_edge_cuts.SetValue(False)
        pcb_sizer.Add(self.clear_edge_cuts, 0, wx.ALL, 3)
        left_sizer.Add(pcb_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        # Screw Hole settings
        screw_box = wx.StaticBox(panel, label="Screw Holes")
        screw_sizer = wx.StaticBoxSizer(screw_box, wx.VERTICAL)
        self.generate_screw_holes = wx.CheckBox(panel, label="Generate holes")
        self.generate_screw_holes.SetValue(False)
        self.generate_screw_holes.Bind(wx.EVT_CHECKBOX, self._on_generate_screw_holes_changed)
        screw_sizer.Add(self.generate_screw_holes, 0, wx.ALL, 3)
        screw_grid = wx.FlexGridSizer(3, 2, 3, 5)
        screw_grid.Add(wx.StaticText(panel, label="Diameter:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.screw_hole_diameter = wx.SpinCtrlDouble(panel, value="2.7", min=1.5, max=5.0, inc=0.1, size=(160, -1))
        screw_grid.Add(self.screw_hole_diameter, 0)
        screw_grid.Add(wx.StaticText(panel, label="Inset:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.screw_hole_inset = wx.SpinCtrlDouble(panel, value="5.0", min=2.0, max=20.0, inc=0.5, size=(160, -1))
        screw_grid.Add(self.screw_hole_inset, 0)
        screw_grid.Add(wx.StaticText(panel, label="Edge Sp:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.screw_edge_spacing = wx.SpinCtrlDouble(panel, value="50.0", min=20.0, max=100.0, inc=1, size=(160, -1))
        screw_grid.Add(self.screw_edge_spacing, 0)
        screw_sizer.Add(screw_grid, 0, wx.ALL, 3)
        self.screw_corner_holes = wx.CheckBox(panel, label="Corner holes")
        self.screw_corner_holes.SetValue(True)
        screw_sizer.Add(self.screw_corner_holes, 0, wx.ALL, 3)
        self.screw_edge_holes = wx.CheckBox(panel, label="Edge holes")
        self.screw_edge_holes.SetValue(False)
        screw_sizer.Add(self.screw_edge_holes, 0, wx.ALL, 3)
        left_sizer.Add(screw_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        columns_sizer.Add(left_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        # ===== RIGHT COLUMN: Top Plate Settings =====
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Top Plate settings
        plate_box = wx.StaticBox(panel, label="Top Plate Generation")
        plate_sizer = wx.StaticBoxSizer(plate_box, wx.VERTICAL)
        
        self.generate_plate = wx.CheckBox(panel, label="Generate top plate")
        self.generate_plate.SetValue(False)
        self.generate_plate.Bind(wx.EVT_CHECKBOX, self._on_generate_plate_changed)
        plate_sizer.Add(self.generate_plate, 0, wx.ALL, 3)
        
        # Plate offset (vertical layout: PCB on top, plate below)
        offset_label = wx.StaticText(panel, label="Plate Position Offset (mm):")
        plate_sizer.Add(offset_label, 0, wx.LEFT | wx.TOP, 5)
        offset_grid = wx.FlexGridSizer(2, 2, 3, 5)
        offset_grid.Add(wx.StaticText(panel, label="X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.plate_offset_x = wx.SpinCtrlDouble(panel, value="0", min=-500, max=500, inc=0.1, size=(160, -1))
        offset_grid.Add(self.plate_offset_x, 0)
        offset_grid.Add(wx.StaticText(panel, label="Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.plate_offset_y = wx.SpinCtrlDouble(panel, value="150", min=0, max=1000, inc=0.1, size=(160, -1))
        offset_grid.Add(self.plate_offset_y, 0)
        plate_sizer.Add(offset_grid, 0, wx.ALL, 3)
        
        # V-cut option
        self.generate_vcut = wx.CheckBox(panel, label="Generate V-cut line between PCB and plate")
        self.generate_vcut.SetValue(True)
        plate_sizer.Add(self.generate_vcut, 0, wx.ALL, 3)
        
        # Cutout size
        cutout_label = wx.StaticText(panel, label="Cutout Size (mm):")
        plate_sizer.Add(cutout_label, 0, wx.LEFT | wx.TOP, 5)
        cutout_grid = wx.FlexGridSizer(3, 2, 3, 5)
        cutout_grid.Add(wx.StaticText(panel, label="W:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cutout_width = wx.SpinCtrlDouble(panel, value="14.0", min=10, max=20, inc=0.1, size=(160, -1))
        cutout_grid.Add(self.cutout_width, 0)
        cutout_grid.Add(wx.StaticText(panel, label="H:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cutout_height = wx.SpinCtrlDouble(panel, value="14.0", min=10, max=20, inc=0.1, size=(160, -1))
        cutout_grid.Add(self.cutout_height, 0)
        cutout_grid.Add(wx.StaticText(panel, label="Corner R:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cutout_corner_radius = wx.SpinCtrlDouble(panel, value="0", min=0, max=5, inc=0.1, size=(160, -1))
        cutout_grid.Add(self.cutout_corner_radius, 0)
        plate_sizer.Add(cutout_grid, 0, wx.ALL, 3)
        
        # Outline settings
        self.generate_outline = wx.CheckBox(panel, label="Generate plate outline")
        self.generate_outline.SetValue(False)
        plate_sizer.Add(self.generate_outline, 0, wx.ALL, 3)
        
        outline_label = wx.StaticText(panel, label="Outline Margin (mm):")
        plate_sizer.Add(outline_label, 0, wx.LEFT | wx.TOP, 5)
        margin_grid = wx.FlexGridSizer(2, 4, 3, 5)
        margin_grid.Add(wx.StaticText(panel, label="Top:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin_top = wx.SpinCtrlDouble(panel, value="5.0", min=0, max=50, inc=0.1, size=(140, -1))
        margin_grid.Add(self.margin_top, 0)
        margin_grid.Add(wx.StaticText(panel, label="Bottom:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin_bottom = wx.SpinCtrlDouble(panel, value="5.0", min=0, max=50, inc=0.1, size=(140, -1))
        margin_grid.Add(self.margin_bottom, 0)
        margin_grid.Add(wx.StaticText(panel, label="Left:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin_left = wx.SpinCtrlDouble(panel, value="5.0", min=0, max=50, inc=0.1, size=(140, -1))
        margin_grid.Add(self.margin_left, 0)
        margin_grid.Add(wx.StaticText(panel, label="Right:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.margin_right = wx.SpinCtrlDouble(panel, value="5.0", min=0, max=50, inc=0.1, size=(140, -1))
        margin_grid.Add(self.margin_right, 0)
        plate_sizer.Add(margin_grid, 0, wx.ALL, 3)
        
        corner_grid = wx.FlexGridSizer(1, 2, 3, 5)
        corner_grid.Add(wx.StaticText(panel, label="Corner R:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.outline_corner_radius = wx.SpinCtrlDouble(panel, value="3.0", min=0, max=20, inc=0.5, size=(140, -1))
        corner_grid.Add(self.outline_corner_radius, 0)
        plate_sizer.Add(corner_grid, 0, wx.ALL, 3)
        
        right_sizer.Add(plate_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        columns_sizer.Add(right_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(columns_sizer, 1, wx.EXPAND)
        
        # Buttons (bottom, full width)
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Apply Layout")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(main_sizer)
        main_sizer.Fit(panel)
        
        # Set up the dialog sizer to contain the scrolled panel
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
    
    def get_settings(self):
        """Return the current settings as a dictionary"""
        return {
            'origin_x': self.origin_x.GetValue(),
            'origin_y': self.origin_y.GetValue(),
            'sw_width': self.sw_width.GetValue(),
            'sw_height': self.sw_height.GetValue(),
            'place_diodes': self.place_diodes.GetValue(),
            'diode_offset_x': self.diode_offset_x.GetValue(),
            'diode_offset_y': self.diode_offset_y.GetValue(),
            'diode_rotation': self.diode_rotation.GetValue(),
            # Top plate settings
            'generate_plate': self.generate_plate.GetValue(),
            'plate_offset_x': self.plate_offset_x.GetValue(),
            'plate_offset_y': self.plate_offset_y.GetValue(),
            'generate_vcut': self.generate_vcut.GetValue(),
            'cutout_width': self.cutout_width.GetValue(),
            'cutout_height': self.cutout_height.GetValue(),
            'cutout_corner_radius': self.cutout_corner_radius.GetValue(),
            'generate_outline': self.generate_outline.GetValue(),
            'margin_top': self.margin_top.GetValue(),
            'margin_bottom': self.margin_bottom.GetValue(),
            'margin_left': self.margin_left.GetValue(),
            'margin_right': self.margin_right.GetValue(),
            'outline_corner_radius': self.outline_corner_radius.GetValue(),
            'clear_edge_cuts': self.clear_edge_cuts.GetValue(),
            # PCB outline settings
            'generate_pcb_outline': self.generate_pcb_outline.GetValue(),
            # Screw hole settings
            'generate_screw_holes': self.generate_screw_holes.GetValue(),
            'screw_hole_diameter': self.screw_hole_diameter.GetValue(),
            'screw_hole_inset': self.screw_hole_inset.GetValue(),
            'screw_edge_spacing': self.screw_edge_spacing.GetValue(),
            'screw_corner_holes': self.screw_corner_holes.GetValue(),
            'screw_edge_holes': self.screw_edge_holes.GetValue(),
        }
    
    def _on_generate_plate_changed(self, event):
        """Enable/disable plate settings based on checkbox"""
        enabled = self.generate_plate.GetValue()
        self.plate_offset_x.Enable(enabled)
        self.plate_offset_y.Enable(enabled)
        self.generate_vcut.Enable(enabled)
        self.cutout_width.Enable(enabled)
        self.cutout_height.Enable(enabled)
        self.cutout_corner_radius.Enable(enabled)
        self.generate_outline.Enable(enabled)
        self.margin_top.Enable(enabled)
        self.margin_bottom.Enable(enabled)
        self.margin_left.Enable(enabled)
        self.margin_right.Enable(enabled)
        self.outline_corner_radius.Enable(enabled)
        self.clear_edge_cuts.Enable(enabled)
    
    def _on_generate_screw_holes_changed(self, event):
        """Enable/disable screw hole settings based on checkbox"""
        enabled = self.generate_screw_holes.GetValue()
        self.screw_hole_diameter.Enable(enabled)
        self.screw_hole_inset.Enable(enabled)
        self.screw_edge_spacing.Enable(enabled)
        self.screw_corner_holes.Enable(enabled)
        self.screw_edge_holes.Enable(enabled)
