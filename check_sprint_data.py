import json
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="pulse_db",
        user="pulse_user",
        password="pulse_password"
    )
    print("✅ Connected to database")
except Exception as e:
    print(f"❌ Database connection error: {e}")
    exit(1)

cursor = conn.cursor(cursor_factory=RealDictCursor)

# Get a recent issue from raw_extraction_data
cursor.execute("""
    SELECT id, payload 
    FROM raw_extraction_data 
    WHERE type = 'jira_single_issue_changelog'
    ORDER BY id DESC 
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    print(f"✅ Found raw data ID: {row['id']}")
    payload = row['payload']

    if 'issue' in payload:
        issue = payload['issue']
        print(f"\n📋 Issue Key: {issue.get('key')}")
        print(f"📋 Issue ID: {issue.get('id')}")

        fields = issue.get('fields', {})

        # Check for sprint field
        sprint_field = fields.get('customfield_10020')
        print(f"\n🔍 customfield_10020 (sprint field):")
        print(f"  Type: {type(sprint_field)}")
        if sprint_field:
            print(f"  Value: {json.dumps(sprint_field, indent=2)}")
        else:
            print(f"  Value: None")

        # Check for other custom fields that might contain sprint data
        print(f"\n🔍 Searching for other sprint-related fields...")
        found_sprint_fields = False
        for key in fields.keys():
            if 'sprint' in key.lower():
                found_sprint_fields = True
                print(f"\n  {key}:")
                print(f"    Type: {type(fields[key])}")
                value_str = json.dumps(fields[key], indent=4)
                if len(value_str) > 500:
                    print(f"    Value: {value_str[:500]}... (truncated)")
                else:
                    print(f"    Value: {value_str}")

        if not found_sprint_fields:
            print("  ❌ No sprint-related fields found")
    else:
        print("❌ No 'issue' key in payload")
else:
    print("❌ No raw data found")

cursor.close()
conn.close()
print("\n✅ Done")

