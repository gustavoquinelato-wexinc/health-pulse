#!/usr/bin/env python3
"""
Fix AAA accessibility colors to have more visible contrast difference.

The current AAA colors are only 10% darker than base colors, making them
visually indistinguishable. This script updates them to be 30% darker
for better visual distinction.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def darken_color(hex_color, factor=0.3):
    """Darken a color by a factor (0.0 to 1.0)"""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    
    return f"#{r:02x}{g:02x}{b:02x}"

def pick_on_color(hex_color, threshold=0.5):
    """Pick optimal text color (black or white) for given background"""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Calculate luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    
    return '#FFFFFF' if luminance < threshold else '#000000'

def lighten_color(hex_color, factor=0.3):
    """Lighten a color by a factor (0.0 to 1.0)"""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    
    return f"#{r:02x}{g:02x}{b:02x}"

def get_adaptive_color(hex_color, defined_in_mode='light'):
    """Create theme-adaptive color for opposite mode"""
    if defined_in_mode == 'light':
        return lighten_color(hex_color, 0.3)
    else:
        return darken_color(hex_color, 0.3)

def calculate_gradient_on_color(color1, color2):
    """Calculate on-color for gradient between two colors"""
    # For simplicity, use the darker color's on-color
    color1_lum = get_luminance(color1)
    color2_lum = get_luminance(color2)
    
    darker_color = color1 if color1_lum < color2_lum else color2
    return pick_on_color(darker_color)

def get_luminance(hex_color):
    """Calculate luminance of a color"""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255

def main():
    # Database connection
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            database=os.getenv('POSTGRES_DB', 'pulse_platform'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🎨 Fixing AAA accessibility colors for better visual distinction...")
        
        # Get all AAA accessibility color records
        cursor.execute("""
            SELECT id, client_id, color_schema_mode, 
                   color1, color2, color3, color4, color5,
                   colors_defined_in_mode
            FROM client_accessibility_colors 
            WHERE accessibility_level = 'AAA'
            ORDER BY client_id, color_schema_mode
        """)
        
        aaa_records = cursor.fetchall()
        print(f"   Found {len(aaa_records)} AAA records to update")
        
        for record in aaa_records:
            print(f"   Updating AAA colors for client {record['client_id']}, mode {record['color_schema_mode']}")
            
            # Get the corresponding base colors from client_color_settings
            cursor.execute("""
                SELECT color1, color2, color3, color4, color5, colors_defined_in_mode
                FROM client_color_settings
                WHERE client_id = %s AND color_schema_mode = %s AND active = TRUE
            """, (record['client_id'], record['color_schema_mode']))
            
            base_record = cursor.fetchone()
            if not base_record:
                print(f"   ⚠️ No base colors found for client {record['client_id']}, mode {record['color_schema_mode']}")
                continue
            
            # Calculate new AAA colors with 30% darkening (more visible)
            new_colors = {}
            for i in range(1, 6):
                base_color = base_record[f'color{i}']
                if base_color:
                    new_colors[f'color{i}'] = darken_color(base_color, 0.3)  # 30% darker
                    new_colors[f'on_color{i}'] = pick_on_color(new_colors[f'color{i}'])
                    new_colors[f'adaptive_color{i}'] = get_adaptive_color(
                        new_colors[f'color{i}'], 
                        base_record['colors_defined_in_mode'] or 'light'
                    )
            
            # Calculate gradient colors
            gradient_pairs = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 1)]
            for from_idx, to_idx in gradient_pairs:
                if new_colors.get(f'color{from_idx}') and new_colors.get(f'color{to_idx}'):
                    new_colors[f'on_gradient_{from_idx}_{to_idx}'] = calculate_gradient_on_color(
                        new_colors[f'color{from_idx}'], 
                        new_colors[f'color{to_idx}']
                    )
            
            # Update the record
            cursor.execute("""
                UPDATE client_accessibility_colors SET
                    color1 = %s, color2 = %s, color3 = %s, color4 = %s, color5 = %s,
                    on_color1 = %s, on_color2 = %s, on_color3 = %s, on_color4 = %s, on_color5 = %s,
                    on_gradient_1_2 = %s, on_gradient_2_3 = %s, on_gradient_3_4 = %s, 
                    on_gradient_4_5 = %s, on_gradient_5_1 = %s,
                    adaptive_color1 = %s, adaptive_color2 = %s, adaptive_color3 = %s, 
                    adaptive_color4 = %s, adaptive_color5 = %s,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                new_colors.get('color1'), new_colors.get('color2'), new_colors.get('color3'), 
                new_colors.get('color4'), new_colors.get('color5'),
                new_colors.get('on_color1'), new_colors.get('on_color2'), new_colors.get('on_color3'), 
                new_colors.get('on_color4'), new_colors.get('on_color5'),
                new_colors.get('on_gradient_1_2'), new_colors.get('on_gradient_2_3'), 
                new_colors.get('on_gradient_3_4'), new_colors.get('on_gradient_4_5'), 
                new_colors.get('on_gradient_5_1'),
                new_colors.get('adaptive_color1'), new_colors.get('adaptive_color2'), 
                new_colors.get('adaptive_color3'), new_colors.get('adaptive_color4'), 
                new_colors.get('adaptive_color5'),
                record['id']
            ))
            
            print(f"   ✅ Updated AAA colors: {base_record['color1']} → {new_colors.get('color1')}")
        
        conn.commit()
        print(f"✅ Successfully updated {len(aaa_records)} AAA accessibility color records")
        print("🎨 AAA colors now have 30% darkening for better visual distinction")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
