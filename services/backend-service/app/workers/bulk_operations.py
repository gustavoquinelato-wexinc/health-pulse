"""
Bulk database operations for transform workers.

Provides optimized bulk insert and update operations using raw SQL
for maximum performance, based on the old ETL service implementation.
"""

import logging
from typing import List, Dict, Any
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BulkOperations:
    """
    Bulk database operations helper class.
    
    Provides optimized bulk insert and update operations using raw SQL
    for maximum performance with PostgreSQL.
    """
    
    @staticmethod
    def bulk_insert(session, table_name: str, data_list: List[Dict[str, Any]], batch_size: int = 100):
        """
        Perform bulk insert using raw SQL for optimal performance.
        
        Args:
            session: Database session
            table_name: Name of the database table
            data_list: List of dictionaries with data to insert
            batch_size: Number of records per batch
        """
        if not data_list:
            return
        
        # Get column names from the first record
        columns = list(data_list[0].keys())
        columns_str = ', '.join(columns)
        
        logger.info(f"Starting bulk insert for {len(data_list)} {table_name} records...")
        
        # Process in batches
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            
            # Create VALUES clause for bulk insert
            values_list = []
            params = {}
            
            for idx, record in enumerate(batch):
                param_prefix = f"p{i}_{idx}_"
                value_placeholders = []
                
                for col in columns:
                    if col == 'id':
                        # Skip ID column for auto-increment
                        continue
                    else:
                        # For all other columns, use the actual values
                        value_placeholders.append(f":{param_prefix}{col}")
                        # Handle unicode encoding for string values
                        value = record[col]
                        if isinstance(value, str):
                            # Ensure proper unicode handling
                            value = value.encode('utf-8', errors='replace').decode('utf-8')
                        params[f"{param_prefix}{col}"] = value
                
                values_list.append(f"({', '.join(value_placeholders)})")
            
            # Execute bulk insert with raw SQL
            insert_columns = [col for col in columns if col != 'id']
            columns_str = ', '.join(insert_columns)
            
            bulk_sql = f"""
                INSERT INTO {table_name} ({columns_str}) 
                VALUES {', '.join(values_list)}
            """
            
            session.execute(text(bulk_sql), params)
            
            # Log progress
            batch_num = i//batch_size + 1
            total_batches = (len(data_list) + batch_size - 1)//batch_size
            if batch_num % 5 == 0 or batch_num == total_batches:
                logger.info(f"[OK] BULK inserted batch {batch_num}/{total_batches} ({len(batch)} {table_name})")
        
        logger.info(f"[COMPLETE] Completed bulk insert of {len(data_list)} {table_name} records")
    
    @staticmethod
    def bulk_update(session, table_name: str, data_list: List[Dict[str, Any]], batch_size: int = 100):
        """
        Perform bulk update using raw SQL for optimal performance.
        
        Args:
            session: Database session
            table_name: Name of the database table
            data_list: List of dictionaries with data to update (must include 'id')
            batch_size: Number of records per batch
        """
        if not data_list:
            return
        
        logger.info(f"Starting bulk update for {len(data_list)} {table_name} records...")
        
        # Process in batches
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            
            # Create individual UPDATE statements for each record
            for idx, record in enumerate(batch):
                if 'id' not in record:
                    logger.warning(f"Skipping update record without ID: {record}")
                    continue
                
                # Build SET clause
                set_clauses = []
                params = {'record_id': record['id']}
                
                for col, value in record.items():
                    if col == 'id':
                        continue  # Skip ID in SET clause
                    
                    set_clauses.append(f"{col} = :{col}")
                    if isinstance(value, str):
                        # Ensure proper unicode handling
                        value = value.encode('utf-8', errors='replace').decode('utf-8')
                    params[col] = value
                
                if set_clauses:
                    update_sql = f"""
                        UPDATE {table_name} 
                        SET {', '.join(set_clauses)}
                        WHERE id = :record_id
                    """
                    session.execute(text(update_sql), params)
            
            # Log progress
            batch_num = i//batch_size + 1
            total_batches = (len(data_list) + batch_size - 1)//batch_size
            if batch_num % 5 == 0 or batch_num == total_batches:
                logger.info(f"[OK] BULK updated batch {batch_num}/{total_batches} ({len(batch)} {table_name})")
        
        logger.info(f"[COMPLETE] Completed bulk update of {len(data_list)} {table_name} records")
    
    @staticmethod
    def bulk_insert_relationships(session, table_name: str, relationships: List[tuple], batch_size: int = 100):
        """
        Perform bulk insert of relationship records.
        
        Args:
            session: Database session
            table_name: Name of the relationship table (e.g., 'projects_wits')
            relationships: List of tuples (id1, id2) representing relationships
            batch_size: Number of records per batch
        """
        if not relationships:
            return
        
        # Determine column names based on table
        if table_name == 'projects_wits':
            col1, col2 = 'project_id', 'wit_id'
        elif table_name == 'projects_statuses':
            col1, col2 = 'project_id', 'status_id'
        else:
            raise ValueError(f"Unsupported relationship table: {table_name}")
        
        logger.info(f"Starting bulk insert for {len(relationships)} {table_name} relationships...")
        
        # Process in batches
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i + batch_size]
            
            # Create VALUES clause for bulk insert
            values_list = []
            params = {}
            
            for idx, (id1, id2) in enumerate(batch):
                param_prefix = f"r{i}_{idx}_"
                values_list.append(f"(:{param_prefix}id1, :{param_prefix}id2)")
                params[f"{param_prefix}id1"] = id1
                params[f"{param_prefix}id2"] = id2
            
            # Execute bulk insert with raw SQL
            bulk_sql = f"""
                INSERT INTO {table_name} ({col1}, {col2}) 
                VALUES {', '.join(values_list)}
                ON CONFLICT ({col1}, {col2}) DO NOTHING
            """
            
            session.execute(text(bulk_sql), params)
            
            # Log progress
            batch_num = i//batch_size + 1
            total_batches = (len(relationships) + batch_size - 1)//batch_size
            if batch_num % 5 == 0 or batch_num == total_batches:
                logger.info(f"[OK] BULK inserted batch {batch_num}/{total_batches} ({len(batch)} {table_name})")
        
        logger.info(f"[COMPLETE] Completed bulk insert of {len(relationships)} {table_name} relationships")
