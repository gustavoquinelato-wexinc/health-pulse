#!/usr/bin/env python3

import sys
import asyncio
sys.path.append('.')
from app.core.database import get_database
from app.models.unified_models import StatusMapping
from app.workers.embedding_worker import EmbeddingWorker

async def test_mapping_embedding():
    database = get_database()
    worker = EmbeddingWorker()

    with database.get_read_session_context() as session:
        record = session.query(StatusMapping).filter(StatusMapping.tenant_id == 1).first()

        if record:
            print(f'Testing record ID {record.id}:')
            print(f'  status_from: {record.status_from}')
            print(f'  status_to: {record.status_to}')
            print(f'  status_category: {record.status_category}')

            entity_data = worker._create_mapping_entity_data(record, 'status_mappings')
            print(f'  entity_data: {entity_data}')

            text = worker._extract_text_content(entity_data, 'status_mappings')
            print(f'  generated_text: "{text}"')

            if not text.strip():
                print('❌ Generated text is empty!')
                return

            print('✅ Generated text looks good')

            # Test embedding generation
            print('Testing embedding generation...')
            try:
                # Initialize hybrid provider first
                worker._initialize_hybrid_provider_sync()

                # Initialize providers for tenant
                await worker.hybrid_provider.initialize_providers(1)

                embedding_vector = await worker._generate_embedding(entity_data, 'status_mappings')
                if embedding_vector:
                    print(f'✅ Embedding generated successfully, length: {len(embedding_vector)}')
                else:
                    print('❌ Embedding generation failed')
            except Exception as e:
                print(f'❌ Error during embedding generation: {e}')
        else:
            print('❌ No status mapping found')

if __name__ == "__main__":
    asyncio.run(test_mapping_embedding())
