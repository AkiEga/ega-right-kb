"""
KLE to KiCAD Action Plugin
--------------------------
Action Plugin class for the KLE to KiCAD Layout plugin.
This integrates with KiCAD's Plugin menu (Tools -> External Plugins).
"""

import pcbnew
import os
import wx

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
            
            # Save to cache
            pcb_path = board.GetFileName() if board.GetFileName() else "Unsaved"
            cache.add_execution_result(kle_path, pcb_path, settings, result)
            
            # Refresh the display
            pcbnew.Refresh()
            
            # Show result
            wx.MessageBox(
                f"Layout completed!\n\n"
                f"Switches placed: {result['switches_placed']}\n"
                f"Diodes placed: {result['diodes_placed']}\n"
                f"Warnings: {result['warnings']}\n\n"
                f"Settings saved to cache.",
                "KLE to KiCAD",
                wx.OK | wx.ICON_INFORMATION
            )
            
        except Exception as e:
            wx.MessageBox(f"Error during layout:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)


class KLE2KiCADSettingsDialog(wx.Dialog):
    """
    Settings dialog for KLE to KiCAD plugin.
    Allows user to configure layout parameters.
    """
    
    def __init__(self, parent, kle_path, cache_manager=None):
        super().__init__(parent, title="KLE to KiCAD Settings", size=(450, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.kle_path = kle_path
        self.cache_manager = cache_manager
        self._init_ui()
        self._load_cached_settings()
        self.SetMinSize((400, 550))
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
    
    def _init_ui(self):
        """Initialize the dialog UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # File info
        file_box = wx.StaticBox(panel, label="Selected File")
        file_sizer = wx.StaticBoxSizer(file_box, wx.VERTICAL)
        file_label = wx.StaticText(panel, label=os.path.basename(self.kle_path))
        file_sizer.Add(file_label, 0, wx.ALL, 5)
        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Last execution info (if available)
        if self.cache_manager:
            last_exec = self.cache_manager.get_last_execution()
            if last_exec:
                history_box = wx.StaticBox(panel, label="Last Execution")
                history_sizer = wx.StaticBoxSizer(history_box, wx.VERTICAL)
                
                timestamp = last_exec.get('timestamp', 'Unknown')[:19].replace('T', ' ')
                last_file = os.path.basename(last_exec.get('kle_file', 'Unknown'))
                switches = last_exec.get('switches_placed', 0)
                diodes = last_exec.get('diodes_placed', 0)
                
                history_text = f"Time: {timestamp}\nFile: {last_file}\nPlaced: {switches} switches, {diodes} diodes"
                history_label = wx.StaticText(panel, label=history_text)
                history_sizer.Add(history_label, 0, wx.ALL, 5)
                main_sizer.Add(history_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Origin settings
        origin_box = wx.StaticBox(panel, label="Origin Position (mm)")
        origin_sizer = wx.StaticBoxSizer(origin_box, wx.VERTICAL)
        
        origin_grid = wx.FlexGridSizer(2, 2, 5, 10)
        origin_grid.Add(wx.StaticText(panel, label="X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.origin_x = wx.SpinCtrlDouble(panel, value="50", min=0, max=500, inc=1)
        origin_grid.Add(self.origin_x, 0, wx.EXPAND)
        origin_grid.Add(wx.StaticText(panel, label="Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.origin_y = wx.SpinCtrlDouble(panel, value="50", min=0, max=500, inc=1)
        origin_grid.Add(self.origin_y, 0, wx.EXPAND)
        origin_sizer.Add(origin_grid, 0, wx.ALL, 5)
        main_sizer.Add(origin_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Switch settings
        switch_box = wx.StaticBox(panel, label="Switch Settings (mm)")
        switch_sizer = wx.StaticBoxSizer(switch_box, wx.VERTICAL)
        
        switch_grid = wx.FlexGridSizer(2, 2, 5, 10)
        switch_grid.Add(wx.StaticText(panel, label="Width:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sw_width = wx.SpinCtrlDouble(panel, value="19.05", min=10, max=30, inc=0.01)
        switch_grid.Add(self.sw_width, 0, wx.EXPAND)
        switch_grid.Add(wx.StaticText(panel, label="Height:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sw_height = wx.SpinCtrlDouble(panel, value="19.05", min=10, max=30, inc=0.01)
        switch_grid.Add(self.sw_height, 0, wx.EXPAND)
        switch_sizer.Add(switch_grid, 0, wx.ALL, 5)
        main_sizer.Add(switch_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Diode settings
        diode_box = wx.StaticBox(panel, label="Diode Settings")
        diode_sizer = wx.StaticBoxSizer(diode_box, wx.VERTICAL)
        
        self.place_diodes = wx.CheckBox(panel, label="Auto-place diodes (D)")
        self.place_diodes.SetValue(True)
        diode_sizer.Add(self.place_diodes, 0, wx.ALL, 5)
        
        diode_grid = wx.FlexGridSizer(3, 2, 5, 10)
        diode_grid.Add(wx.StaticText(panel, label="Offset X (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_offset_x = wx.SpinCtrlDouble(panel, value="0", min=-20, max=20, inc=0.1)
        diode_grid.Add(self.diode_offset_x, 0, wx.EXPAND)
        diode_grid.Add(wx.StaticText(panel, label="Offset Y (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_offset_y = wx.SpinCtrlDouble(panel, value="5.08", min=-20, max=20, inc=0.1)
        diode_grid.Add(self.diode_offset_y, 0, wx.EXPAND)
        diode_grid.Add(wx.StaticText(panel, label="Rotation (deg):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.diode_rotation = wx.SpinCtrlDouble(panel, value="90", min=0, max=360, inc=1)
        diode_grid.Add(self.diode_rotation, 0, wx.EXPAND)
        diode_sizer.Add(diode_grid, 0, wx.ALL, 5)
        main_sizer.Add(diode_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Apply Layout")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(main_sizer)
    
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
        }
