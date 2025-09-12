#!/usr/bin/env python3
"""
Embedding Model Consistency Validator

Validates that all vectors for a tenant use the same embedding model and dimensions.
Provides migration path for switching models.
"""

from app.core.database import get_database
from app.models.unified_models import QdrantVector, Integration
from sqlalchemy import func, distinct
import asyncio

async def validate_embedding_consistency():
    """Check for mixed embedding models per tenant"""
    print("🔍 Validating embedding model consistency...")
    
    database = get_database()
    with database.get_read_session_context() as session:
        
        # Check for mixed models per tenant
        mixed_models = session.query(
            QdrantVector.tenant_id,
            func.count(distinct(QdrantVector.embedding_model)).label('model_count'),
            func.count(distinct(QdrantVector.embedding_provider)).label('provider_count'),
            func.array_agg(distinct(QdrantVector.embedding_model)).label('models'),
            func.array_agg(distinct(QdrantVector.embedding_provider)).label('providers')
        ).group_by(QdrantVector.tenant_id).having(
            func.count(distinct(QdrantVector.embedding_model)) > 1
        ).all()
        
        if mixed_models:
            print("🚨 CRITICAL: Mixed embedding models detected!")
            for result in mixed_models:
                print(f"   Tenant {result.tenant_id}: {result.model_count} models, {result.provider_count} providers")
                print(f"   Models: {result.models}")
                print(f"   Providers: {result.providers}")
            
            return False
        else:
            print("✅ All tenants use consistent embedding models")
            
            # Show current model usage
            model_usage = session.query(
                QdrantVector.tenant_id,
                QdrantVector.embedding_model,
                QdrantVector.embedding_provider,
                func.count(QdrantVector.id).label('vector_count')
            ).group_by(
                QdrantVector.tenant_id,
                QdrantVector.embedding_model,
                QdrantVector.embedding_provider
            ).all()
            
            print("\n📊 Current embedding model usage:")
            for usage in model_usage:
                print(f"   Tenant {usage.tenant_id}: {usage.embedding_model} ({usage.embedding_provider}) - {usage.vector_count:,} vectors")
            
            return True

async def recommend_migration_strategy():
    """Recommend strategy for handling mixed models"""
    print("\n💡 Migration Strategy Recommendations:")
    
    print("\n🔄 Option 1: Re-vectorize All Data (Recommended)")
    print("   - Choose one embedding model per tenant")
    print("   - Delete all existing vectors")
    print("   - Re-generate all vectors with chosen model")
    print("   - Pros: Clean, consistent, optimal search quality")
    print("   - Cons: Requires processing time and API costs")
    
    print("\n🔄 Option 2: Separate Collections Per Model")
    print("   - Create separate Qdrant collections per model")
    print("   - Search multiple collections and merge results")
    print("   - Pros: No re-processing needed")
    print("   - Cons: Complex search logic, suboptimal results")
    
    print("\n🔄 Option 3: Model-Specific Tenants")
    print("   - Assign embedding model at tenant level")
    print("   - Prevent model switching once vectors exist")
    print("   - Pros: Prevents future inconsistencies")
    print("   - Cons: Less flexibility")

async def estimate_storage_growth():
    """Estimate qdrant_vectors table growth"""
    print("\n📈 Storage Growth Analysis:")
    
    database = get_database()
    with database.get_read_session_context() as session:
        
        # Current vector count
        current_vectors = session.query(func.count(QdrantVector.id)).scalar()
        print(f"   Current vectors: {current_vectors:,}")
        
        # Vectors per tenant
        tenant_vectors = session.query(
            QdrantVector.tenant_id,
            func.count(QdrantVector.id).label('vector_count')
        ).group_by(QdrantVector.tenant_id).all()
        
        if tenant_vectors:
            avg_vectors_per_tenant = sum(tv.vector_count for tv in tenant_vectors) / len(tenant_vectors)
            print(f"   Average vectors per tenant: {avg_vectors_per_tenant:,.0f}")
            
            # Growth projections
            projections = [10, 50, 100, 500, 1000]
            print(f"\n   Growth projections:")
            for tenant_count in projections:
                total_vectors = tenant_count * avg_vectors_per_tenant
                storage_mb = total_vectors * 0.5  # Rough estimate: 0.5KB per vector record
                print(f"   {tenant_count:,} tenants: {total_vectors:,.0f} vectors (~{storage_mb:,.0f} MB)")
        
        # Vectors per table type
        table_vectors = session.query(
            QdrantVector.table_name,
            func.count(QdrantVector.id).label('vector_count')
        ).group_by(QdrantVector.table_name).order_by(func.count(QdrantVector.id).desc()).all()
        
        if table_vectors:
            print(f"\n   Vectors by table type:")
            for tv in table_vectors:
                print(f"   {tv.table_name}: {tv.vector_count:,} vectors")

if __name__ == "__main__":
    print("🚀 Starting embedding consistency validation...")
    print("=" * 60)
    
    asyncio.run(validate_embedding_consistency())
    asyncio.run(recommend_migration_strategy())
    asyncio.run(estimate_storage_growth())
    
    print("\n" + "=" * 60)
    print("✅ Validation complete!")
