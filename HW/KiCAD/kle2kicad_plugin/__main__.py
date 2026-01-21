"""
KLE to KiCAD Plugin - Command Line Interface
--------------------------------------------
Allows running the plugin standalone for testing or batch processing.

Usage:
    python -m kle2kicad_plugin <kle_json_path> <kicad_pcb_path> [options]

Example:
    python -m kle2kicad_plugin layout.json board.kicad_pcb --origin-x 50 --origin-y 50
"""

import argparse
import sys
import os


def main():
    parser = argparse.ArgumentParser(
        description="KLE to KiCAD - Import keyboard layout from KLE JSON"
    )
    parser.add_argument(
        "kle_json",
        help="Path to the keyboard-layout-editor JSON file"
    )
    parser.add_argument(
        "kicad_pcb",
        help="Path to the KiCAD PCB file"
    )
    parser.add_argument(
        "--origin-x", type=float, default=50.0,
        help="Origin X position in mm (default: 50)"
    )
    parser.add_argument(
        "--origin-y", type=float, default=50.0,
        help="Origin Y position in mm (default: 50)"
    )
    parser.add_argument(
        "--sw-width", type=float, default=19.05,
        help="Switch width/pitch in mm (default: 19.05 for Cherry MX)"
    )
    parser.add_argument(
        "--sw-height", type=float, default=19.05,
        help="Switch height/pitch in mm (default: 19.05 for Cherry MX)"
    )
    parser.add_argument(
        "--no-diodes", action="store_true",
        help="Don't place diodes"
    )
    parser.add_argument(
        "--diode-offset-x", type=float, default=0.0,
        help="Diode X offset from switch center in mm (default: 0)"
    )
    parser.add_argument(
        "--diode-offset-y", type=float, default=5.08,
        help="Diode Y offset from switch center in mm (default: 5.08)"
    )
    parser.add_argument(
        "--diode-rotation", type=float, default=90.0,
        help="Diode rotation in degrees (default: 90)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output PCB file path (default: overwrites input)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and report without modifying the PCB"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.kle_json):
        print(f"Error: KLE JSON file not found: {args.kle_json}")
        sys.exit(1)
    
    if not os.path.exists(args.kicad_pcb):
        print(f"Error: KiCAD PCB file not found: {args.kicad_pcb}")
        sys.exit(1)
    
    # Import pcbnew (only available in KiCAD's Python environment)
    try:
        import pcbnew
    except ImportError:
        print("Error: pcbnew module not found.")
        print("This script must be run from KiCAD's Python environment.")
        print("Try running from KiCAD's scripting console or use the plugin directly.")
        sys.exit(1)
    
    from .kle2kicad_core import KLE2KiCADCore, KLEParser
    
    # Build settings
    settings = {
        'origin_x': args.origin_x,
        'origin_y': args.origin_y,
        'sw_width': args.sw_width,
        'sw_height': args.sw_height,
        'place_diodes': not args.no_diodes,
        'diode_offset_x': args.diode_offset_x,
        'diode_offset_y': args.diode_offset_y,
        'diode_rotation': args.diode_rotation,
    }
    
    print(f"KLE to KiCAD Layout Tool")
    print(f"=" * 40)
    print(f"KLE JSON: {args.kle_json}")
    print(f"KiCAD PCB: {args.kicad_pcb}")
    print(f"Settings: {settings}")
    print()
    
    # Parse KLE JSON first (works without pcbnew)
    print("Parsing KLE JSON...")
    parser = KLEParser(args.kle_json)
    keys = parser.parse()
    print(f"Found {len(keys)} keys:")
    for key in keys:
        print(f"  {key.ref}: pos=({key.x:.2f}, {key.y:.2f}), size=({key.width:.1f}x{key.height:.1f}), rot={key.rotation}°")
    print()
    
    if args.dry_run:
        print("Dry run - no changes made to PCB")
        sys.exit(0)
    
    # Load the board
    print("Loading KiCAD PCB...")
    board = pcbnew.LoadBoard(args.kicad_pcb)
    
    # Execute layout
    print("Placing footprints...")
    core = KLE2KiCADCore(board, args.kle_json, settings)
    result = core.execute()
    
    print(f"\nResults:")
    print(f"  Switches placed: {result['switches_placed']}")
    print(f"  Diodes placed: {result['diodes_placed']}")
    
    if result['warnings']:
        print(f"\nWarnings ({result['warnings']}):")
        for warning in result['warning_messages']:
            print(f"  - {warning}")
    
    # Save the board
    output_path = args.output if args.output else args.kicad_pcb
    print(f"\nSaving to: {output_path}")
    pcbnew.SaveBoard(output_path, board)
    
    print("Done!")


if __name__ == "__main__":
    main()
