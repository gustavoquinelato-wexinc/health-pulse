#!/usr/bin/env python3
"""
Check if projects, wits, and statuses are in the database for embedding processing.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'backend-service'))

from app.core.database import get_database
from app.models.unified_models import Project, Wit, Status, WorkItem

def check_entities():
    """Check if entities exist in the database."""
    database = get_database()
    
    tenant_id = 1
    
    print(f"\n{'='*60}")
    print(f"Checking entities for tenant_id={tenant_id}")
    print(f"{'='*60}\n")
    
    with database.get_read_session_context() as session:
        # Check projects
        projects = session.query(Project).filter(Project.tenant_id == tenant_id).all()
        print(f"📊 Projects: {len(projects)} found")
        if projects:
            for p in projects[:5]:
                print(f"   - ID: {p.id}, External ID: {p.external_id}, Name: {p.name}")
            if len(projects) > 5:
                print(f"   ... and {len(projects) - 5} more")
        
        # Check wits
        wits = session.query(Wit).filter(Wit.tenant_id == tenant_id).all()
        print(f"\n📊 WITs: {len(wits)} found")
        if wits:
            for w in wits[:5]:
                print(f"   - ID: {w.id}, External ID: {w.external_id}, Name: {w.original_name}")
            if len(wits) > 5:
                print(f"   ... and {len(wits) - 5} more")
        
        # Check statuses
        statuses = session.query(Status).filter(Status.tenant_id == tenant_id).all()
        print(f"\n📊 Statuses: {len(statuses)} found")
        if statuses:
            for s in statuses[:5]:
                print(f"   - ID: {s.id}, External ID: {s.external_id}, Name: {s.original_name}")
            if len(statuses) > 5:
                print(f"   ... and {len(statuses) - 5} more")
        
        # Check work items
        work_items = session.query(WorkItem).filter(WorkItem.tenant_id == tenant_id).all()
        print(f"\n📊 Work Items: {len(work_items)} found")
        if work_items:
            for wi in work_items[:5]:
                print(f"   - ID: {wi.id}, External ID: {wi.external_id}, Key: {wi.key}")
            if len(work_items) > 5:
                print(f"   ... and {len(work_items) - 5} more")
        
        # Check qdrant_vectors table
        from app.models.unified_models import QdrantVector
        vectors = session.query(QdrantVector).filter(QdrantVector.tenant_id == tenant_id).all()
        print(f"\n📊 Qdrant Vectors: {len(vectors)} found")
        if vectors:
            for v in vectors[:5]:
                print(f"   - ID: {v.id}, Entity Type: {v.entity_type}, Entity ID: {v.entity_id}")
            if len(vectors) > 5:
                print(f"   ... and {len(vectors) - 5} more")
        
        print(f"\n{'='*60}\n")

if __name__ == '__main__':
    check_entities()

