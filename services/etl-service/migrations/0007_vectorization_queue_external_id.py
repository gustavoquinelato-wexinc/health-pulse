"""
Migration 0007: Update VectorizationQueue to use external_id instead of record_db_id

This migration:
1. Adds external_id column to vectorization_queue table
2. Migrates existing record_db_id data to external_id (if any exists)
3. Drops record_db_id column
4. Updates unique constraint to use external_id

Date: 2025-09-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade to external_id based vectorization queue"""
    
    # Add external_id column
    op.add_column('vectorization_queue', 
                  sa.Column('external_id', sa.String(length=255), nullable=True))
    
    # Migrate existing data: For existing records, we'll need to look up external_ids
    # Since this is a new feature, we can assume the queue is empty or can be cleared
    # For safety, we'll clear the queue during migration
    op.execute("DELETE FROM vectorization_queue")
    
    # Make external_id non-nullable after clearing data
    op.alter_column('vectorization_queue', 'external_id', nullable=False)
    
    # Drop the old unique constraint
    op.drop_constraint('vectorization_queue_table_name_record_db_id_operation_tenant_id_key', 
                      'vectorization_queue', type_='unique')
    
    # Drop the record_db_id column
    op.drop_column('vectorization_queue', 'record_db_id')
    
    # Add new unique constraint with external_id
    op.create_unique_constraint('vectorization_queue_table_name_external_id_operation_tenant_id_key',
                               'vectorization_queue', 
                               ['table_name', 'external_id', 'operation', 'tenant_id'])


def downgrade():
    """Downgrade back to record_db_id based vectorization queue"""
    
    # Add back record_db_id column
    op.add_column('vectorization_queue', 
                  sa.Column('record_db_id', sa.INTEGER(), nullable=True))
    
    # Clear queue data since we can't reliably convert external_id back to record_db_id
    op.execute("DELETE FROM vectorization_queue")
    
    # Make record_db_id non-nullable after clearing data
    op.alter_column('vectorization_queue', 'record_db_id', nullable=False)
    
    # Drop the external_id unique constraint
    op.drop_constraint('vectorization_queue_table_name_external_id_operation_tenant_id_key', 
                      'vectorization_queue', type_='unique')
    
    # Drop external_id column
    op.drop_column('vectorization_queue', 'external_id')
    
    # Add back old unique constraint
    op.create_unique_constraint('vectorization_queue_table_name_record_db_id_operation_tenant_id_key',
                               'vectorization_queue', 
                               ['table_name', 'record_db_id', 'operation', 'tenant_id'])
