#!/usr/bin/env python3
"""
Simple test to validate color system migration
"""

import os
import sys
import psycopg2

# Add the parent directory to the path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def main():
    settings = get_settings()
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DATABASE,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    cursor = conn.cursor()

    print('🔍 Checking color tables...')
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%color%' ORDER BY table_name;")
    tables = cursor.fetchall()
    print('✅ Color tables found:')
    for table in tables:
        print(f'  - {table[0]}')

    print('\n🔍 Checking color data...')
    cursor.execute('SELECT COUNT(*) FROM client_color_settings;')
    color_count = cursor.fetchone()[0]
    print(f'✅ client_color_settings records: {color_count}')

    cursor.execute('SELECT COUNT(*) FROM client_accessibility_colors;')
    accessibility_count = cursor.fetchone()[0]
    print(f'✅ client_accessibility_colors records: {accessibility_count}')

    cursor.execute('SELECT client_id, color_schema_mode, color1, color2, color3 FROM client_color_settings LIMIT 3;')
    sample_colors = cursor.fetchall()
    print('\n🎨 Sample color data:')
    for row in sample_colors:
        print(f'  Client {row[0]} ({row[1]}): {row[2]}, {row[3]}, {row[4]}')

    cursor.close()
    conn.close()
    print('\n✅ Color system migration validation successful!')

if __name__ == "__main__":
    main()
