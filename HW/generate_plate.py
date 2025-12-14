import json
import sys

def generate_svg(json_path, svg_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            layout = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    keys = []
    current_y = 0.0
    
    # 1u size in mm
    U = 19.05
    HOLE_SIZE = 14.0
    
    # To calculate bounding box
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')

    for row in layout:
        if isinstance(row, dict):
            continue # Skip metadata
            
        current_x = 0.0
        
        # Default props for the key
        w = 1.0
        h = 1.0
        
        for item in row:
            if isinstance(item, dict):
                # Update state
                if 'x' in item: current_x += item['x']
                if 'y' in item: current_y += item['y']
                if 'w' in item: w = item['w']
                if 'h' in item: h = item['h']
            else:
                # Key "item"
                # Calculate position
                # Center of the key
                center_x = (current_x + w / 2.0) * U
                center_y = (current_y + h / 2.0) * U
                
                # Store key info
                keys.append({
                    'label': item,
                    'cx': center_x,
                    'cy': center_y,
                    'w': w,
                    'h': h,
                    'x': current_x * U,
                    'y': current_y * U,
                    'width': w * U,
                    'height': h * U
                })
                
                # Update bounds
                min_x = min(min_x, current_x * U)
                min_y = min(min_y, current_y * U)
                max_x = max(max_x, (current_x + w) * U)
                max_y = max(max_y, (current_y + h) * U)
                
                # Advance x
                current_x += w
                
                # Reset w/h to defaults
                w = 1.0
                h = 1.0
        
        current_y += 1.0

    # Margin for the plate
    MARGIN = 5.0
    plate_min_x = min_x - MARGIN
    plate_min_y = min_y - MARGIN
    plate_max_x = max_x + MARGIN
    plate_max_y = max_y + MARGIN
    
    width = plate_max_x - plate_min_x
    height = plate_max_y - plate_min_y
    
    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="{plate_min_x} {plate_min_y} {width} {height}">',
        f'  <!-- Generated from {json_path} -->',
        f'  <g id="plate_outline" style="stroke:black; fill:none; stroke-width:0.5">',
        f'    <rect x="{plate_min_x}" y="{plate_min_y}" width="{width}" height="{height}" rx="3" ry="3" />',
        f'  </g>',
        f'  <g id="switches" style="stroke:red; fill:none; stroke-width:0.1">',
    ]
    
    for key in keys:
        # Draw switch hole
        hx = key['cx'] - HOLE_SIZE / 2.0
        hy = key['cy'] - HOLE_SIZE / 2.0
        svg_content.append(f'    <rect x="{hx}" y="{hy}" width="{HOLE_SIZE}" height="{HOLE_SIZE}" />')
        
    svg_content.append('  </g>')
    
    # Optional: Keycap outlines for reference
    svg_content.append('  <g id="keycaps" style="stroke:blue; fill:none; stroke-width:0.1; opacity:0.5">')
    for key in keys:
        svg_content.append(f'    <rect x="{key["x"]}" y="{key["y"]}" width="{key["width"]}" height="{key["height"]}" />')
    svg_content.append('  </g>')
    
    svg_content.append('</svg>')
    
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_content))
    
    print(f"SVG generated at {svg_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_plate.py <input_json> <output_svg>")
    else:
        generate_svg(sys.argv[1], sys.argv[2])
