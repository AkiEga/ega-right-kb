# KLE to KiCAD Plugin
# Keyboard Layout Editor JSON to KiCAD PCB Layout Plugin
#
# This plugin imports keyboard layouts from keyboard-layout-editor.com JSON files
# and automatically positions switch (SW) and diode (D) footprints in KiCAD.

from .kle2kicad_action import KLE2KiCADAction

# Register the plugin to KiCAD PCB Editor
KLE2KiCADAction().register()
