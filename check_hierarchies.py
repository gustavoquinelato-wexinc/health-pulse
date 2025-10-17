#!/usr/bin/env python3

import sys
sys.path.append('.')
from app.core.database import get_database
from app.models.unified_models import WitHierarchy

def check_hierarchies():
    database = get_database()
    with database.get_read_session_context() as session:
        records = session.query(WitHierarchy).filter(WitHierarchy.tenant_id == 1).all()
        
        print(f'Found {len(records)} wits_hierarchies records:')
        for record in records:
            print(f'  ID {record.id}: hierarchy_name="{record.hierarchy_name}", level={record.level}, parent_id={record.parent_id}')

if __name__ == "__main__":
    check_hierarchies()
