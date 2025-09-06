"""
Bulk Database Operations

Optimized bulk insert and update operations for Jira ETL.
Uses raw SQL for maximum performance with Snowflake/PostgreSQL.
"""

from sqlalchemy import text
from app.core.logging_config import JobLogger
# Phase 3-1: Removed schema compatibility - clean architecture


def perform_bulk_insert(session, model_class, data_list, table_name, job_logger: JobLogger, batch_size=100):
    """
    Perform true bulk insert using raw SQL for optimal performance with async yielding.

    Args:
        session: Database session
        model_class: SQLAlchemy model class
        data_list: List of dictionaries with data to insert
        table_name: Name of the database table
        job_logger: Logger instance
        batch_size: Number of records per batch
    """
    if not data_list:
        return

    import asyncio

    # Get column names from the first record
    columns = list(data_list[0].keys())

    # Create the base INSERT statement
    columns_str = ', '.join(columns)

    job_logger.progress(f"Starting bulk insert for {len(data_list)} {table_name} records...")

    # Phase 3-1: Clean architecture - no schema compatibility validation needed
    job_logger.progress(f"[BULK] Processing {len(data_list)} {table_name} records for bulk insert")

    # Process in batches
    for i in range(0, len(data_list), batch_size):
        # Add small delay to prevent blocking (synchronous)
        import time
        time.sleep(0.001)  # 1ms delay
        batch = data_list[i:i + batch_size]
        
        # Create VALUES clause for bulk insert
        values_list = []
        params = {}
        
        for idx, record in enumerate(batch):
            param_prefix = f"p{i}_{idx}_"
            
            # Handle primary key columns (use sequence only for actual primary keys)
            # Foreign key columns (like project_id in issues table) should use actual values, not sequences
            value_placeholders = []
            for col in columns:
                # Only use sequences for actual primary key columns in their respective tables
                if ((col == 'id' and table_name == 'issues') or
                    (col == 'id' and table_name == 'issuetypes') or
                    (col == 'id' and table_name == 'projects') or
                    (col == 'id' and table_name == 'statuses') or
                    (col == 'id' and table_name == 'integrations') or
                    (col == 'id' and table_name == 'pull_requests') or
                    (col == 'id' and table_name == 'issue_changelogs') or
                    (col == 'id' and table_name == 'dev_data')):

                    # Use sequence for primary key columns
                    if table_name == 'issuetypes':
                        sequence_name = "issuetypes_id_seq"
                    elif table_name == 'projects':
                        sequence_name = "projects_id_seq"
                    elif table_name == 'statuses':
                        sequence_name = "statuses_id_seq"
                    elif table_name == 'issues':
                        sequence_name = "issues_id_seq"
                    elif table_name == 'integrations':
                        sequence_name = "integrations_id_seq"
                    elif table_name == 'pull_requests':
                        sequence_name = "pullrequests_id_seq"
                    elif table_name == 'issue_changelogs':
                        sequence_name = "issue_changelogs_id_seq"
                    elif table_name == 'dev_data':
                        sequence_name = "devdata_id_seq"

                    value_placeholders.append(f"{sequence_name}.nextval")
                else:
                    # For all other columns (including foreign keys), use the actual values
                    value_placeholders.append(f":{param_prefix}{col}")
                    # Handle unicode encoding for string values
                    value = record[col]
                    if isinstance(value, str):
                        # Ensure proper unicode handling
                        value = value.encode('utf-8', errors='replace').decode('utf-8')
                    params[f"{param_prefix}{col}"] = value
            
            values_list.append(f"({', '.join(value_placeholders)})")
        
        # Execute bulk insert with raw SQL
        bulk_sql = f"""
            INSERT INTO {table_name} ({columns_str}) 
            VALUES {', '.join(values_list)}
        """
        
        session.execute(text(bulk_sql), params)
        # Only log every 5th batch to reduce verbosity
        batch_num = i//batch_size + 1
        total_batches = (len(data_list) + batch_size - 1)//batch_size
        if batch_num % 5 == 0 or batch_num == total_batches:
            job_logger.progress(f"[OK] BULK inserted batch {batch_num}/{total_batches} ({len(batch)} {table_name})")

    job_logger.progress(f"[COMPLETE] Completed REAL bulk insert of {len(data_list)} {table_name} records")


def perform_bulk_delete_relationships(session, table_name, relationships_to_delete, job_logger: JobLogger, batch_size=100):
    """
    Perform bulk delete of relationship records using raw SQL with async yielding.

    Args:
        session: Database session
        table_name: Name of the relationship table (e.g., 'projects_issuetypes', 'projects_statuses')
        relationships_to_delete: Set of tuples (id1, id2) representing relationships to delete
        job_logger: Logger instance
        batch_size: Number of records per batch
    """
    if not relationships_to_delete:
        return

    import asyncio

    relationships_list = list(relationships_to_delete)
    job_logger.progress(f"[DELETE] Starting bulk delete for {len(relationships_list)} {table_name} relationships...")

    # Determine column names based on table
    if table_name == 'projects_issuetypes':
        col1, col2 = 'project_id', 'wit_id'
    elif table_name == 'projects_statuses':
        col1, col2 = 'project_id', 'status_id'
    else:
        raise ValueError(f"Unsupported relationship table: {table_name}")

    # Process in batches
    for i in range(0, len(relationships_list), batch_size):
        # Add small delay to prevent blocking (synchronous)
        import time
        time.sleep(0.001)  # 1ms delay
        batch = relationships_list[i:i + batch_size]

        # Create WHERE conditions for bulk delete
        where_conditions = []
        params = {}

        for idx, (id1, id2) in enumerate(batch):
            param_prefix = f"d{i}_{idx}_"
            where_conditions.append(f"({col1} = :{param_prefix}id1 AND {col2} = :{param_prefix}id2)")
            params[f"{param_prefix}id1"] = id1
            params[f"{param_prefix}id2"] = id2

        # Execute bulk delete with raw SQL
        bulk_delete_sql = f"""
            DELETE FROM {table_name}
            WHERE {' OR '.join(where_conditions)}
        """

        result = session.execute(text(bulk_delete_sql), params)
        deleted_count = result.rowcount
        # Only log every 5th batch to reduce verbosity
        batch_num = i//batch_size + 1
        total_batches = (len(relationships_list) + batch_size - 1)//batch_size
        if batch_num % 5 == 0 or batch_num == total_batches:
            job_logger.progress(f"[OK] BULK deleted batch {batch_num}/{total_batches} ({deleted_count} {table_name})")

    job_logger.progress(f"[COMPLETE] Completed bulk delete of {len(relationships_list)} {table_name} relationships")
