#!/usr/bin/env python3

import sys
import time
sys.path.append('.')
from app.etl.queue.queue_manager import QueueManager
from app.core.database import get_database
from app.models.unified_models import QdrantVector

def test_all_mapping_tables():
    """Test embedding for all 4 mapping tables with improved rate limiting."""
    
    queue_manager = QueueManager()
    database = get_database()
    
    # Define all mapping tables to test
    mapping_tables = [
        'status_mappings',
        'wits_mappings', 
        'wits_hierarchies',
        'workflows'
    ]
    
    print("🧪 Testing all mapping tables with improved rate limiting and retry logic...")
    print("=" * 80)
    
    for table_name in mapping_tables:
        print(f"\n📋 Processing {table_name}...")
        
        # Clear existing vectors for this table
        with database.get_write_session_context() as session:
            deleted = session.query(QdrantVector).filter(
                QdrantVector.tenant_id == 1,
                QdrantVector.table_name == table_name
            ).delete()
            session.commit()
            print(f"🗑️ Cleared {deleted} existing {table_name} vectors")
        
        # Queue the table for embedding
        success = queue_manager.publish_mapping_table_embedding(
            tenant_id=1,
            table_name=table_name
        )
        
        if success:
            print(f"✅ Successfully queued {table_name}")
            
            # Wait for processing (longer for larger tables)
            wait_time = 60 if table_name == 'status_mappings' else 30
            print(f"⏳ Waiting {wait_time}s for processing...")
            time.sleep(wait_time)
            
            # Check results
            with database.get_read_session_context() as session:
                count = session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == 1,
                    QdrantVector.table_name == table_name
                ).count()
                
                print(f"📊 {table_name}: {count} vectors embedded")
                
                # Expected counts (approximate)
                expected = {
                    'status_mappings': 113,
                    'wits_mappings': 28,
                    'wits_hierarchies': 6,
                    'workflows': 12
                }
                
                if count >= expected[table_name]:
                    print(f"🎉 SUCCESS: All {table_name} records embedded!")
                elif count > expected[table_name] * 0.8:
                    print(f"🔥 Great progress: {count}/{expected[table_name]} records")
                elif count > expected[table_name] * 0.5:
                    print(f"⚠️ Partial success: {count}/{expected[table_name]} records")
                else:
                    print(f"❌ Limited success: {count}/{expected[table_name]} records")
        else:
            print(f"❌ Failed to queue {table_name}")
    
    print("\n" + "=" * 80)
    print("📈 FINAL SUMMARY:")
    
    # Final summary of all mapping tables
    with database.get_read_session_context() as session:
        total_vectors = 0
        for table_name in mapping_tables:
            count = session.query(QdrantVector).filter(
                QdrantVector.tenant_id == 1,
                QdrantVector.table_name == table_name
            ).count()
            total_vectors += count
            print(f"  📋 {table_name}: {count} vectors")
        
        print(f"\n🎯 TOTAL MAPPING VECTORS: {total_vectors}")
        
        if total_vectors >= 150:  # Approximate total expected
            print("🎉 EXCELLENT: All mapping tables successfully embedded!")
        elif total_vectors >= 100:
            print("🔥 GREAT: Most mapping tables embedded successfully!")
        elif total_vectors >= 50:
            print("⚠️ PARTIAL: Some mapping tables embedded successfully")
        else:
            print("❌ LIMITED: Few mapping tables embedded successfully")

if __name__ == "__main__":
    test_all_mapping_tables()
