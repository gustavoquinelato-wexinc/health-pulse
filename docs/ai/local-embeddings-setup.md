# Local Embeddings Setup Guide

This guide explains how to download and configure local embedding models as an alternative to external (paid) embeddings.

## 🎯 Overview

**Current Configuration:**
- **Active**: Azure 3-small (`azure-text-embedding-3-small`, 1536D)
- **Available**: MPNet base-v2 (`all-mpnet-base-v2`, 768D) - requires download

**Benefits of Local Embeddings:**
- ✅ **Free**: No API costs after initial download
- ✅ **Privacy**: No external API calls
- ✅ **Offline**: Works without internet connection
- ✅ **Quality**: 768 dimensions (2x better than all-MiniLM-L6-v2)

**Drawbacks:**
- ❌ **Lower Quality**: 768D vs 1536D external embeddings
- ❌ **Storage**: ~3.6GB disk space required
- ❌ **Setup**: Manual download and configuration required

## 📥 Download Local Model

### Step 1: Download all-mpnet-base-v2 Model

```bash
# Navigate to backend service
cd services/backend-service

# Create models directory (if not exists)
mkdir -p models/sentence-transformers

# Navigate to models directory
cd models/sentence-transformers

# Clone the model repository (requires git-lfs)
git lfs install
git -c http.sslVerify=false clone https://huggingface.co/sentence-transformers/all-mpnet-base-v2

# Verify download
ls -la all-mpnet-base-v2/
```

**Expected Output:**
```
all-mpnet-base-v2/
├── 1_Pooling/
├── config.json
├── model.safetensors
├── pytorch_model.bin
├── tokenizer.json
├── vocab.txt
└── ... (other model files)
```

### Step 2: Test Local Model

```bash
# Test the downloaded model
cd services/backend-service
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('models/sentence-transformers/all-mpnet-base-v2')
embeddings = model.encode(['test sentence'])
print(f'✅ Model working! Dimensions: {embeddings.shape[1]}')
"
```

## 🔄 Switch to Local Embeddings

### Option A: Database Update (Recommended)

```python
# Update via Python script
cd services/backend-service
python -c "
from app.core.database import get_database
from app.models.unified_models import Integration

database = get_database()
with database.get_write_session_context() as session:
    
    # Choose tenant (1=WEX, 2=Apple, 3=Google)
    tenant_id = 1
    
    # Deactivate external embeddings
    external = session.query(Integration).filter(
        Integration.tenant_id == tenant_id,
        Integration.provider == 'Azure 3-small'
    ).first()
    if external:
        external.active = False
        print(f'❌ Deactivated external embeddings')

    # Activate local embeddings
    local = session.query(Integration).filter(
        Integration.tenant_id == tenant_id,
        Integration.provider == 'MPNet base-v2'
    ).first()
    if local:
        local.active = True
        print(f'✅ Activated local embeddings')
    
    session.commit()
    print(f'🎯 Tenant {tenant_id} now using local embeddings')
"
```

### Option B: Migration Update

Update the migration files to set local as default:

```python
# In services/backend-service/scripts/migrations/000X_*.py
# Change these lines:

# FROM:
tenant_id, False  # Set to inactive - using external embeddings as primary

# TO:
tenant_id, True   # Set to active - using local embeddings as primary

# AND:

# FROM:
tenant_id, True   # Set to active - external embeddings as primary

# TO:
tenant_id, False  # Set to inactive - using local embeddings as primary
```

## 🧪 Verify Local Embeddings

```python
# Test local embeddings via API
cd services/backend-service
python -c "
import asyncio
from app.core.database import get_database
from app.ai.hybrid_provider_manager import HybridProviderManager

async def test_local():
    database = get_database()
    with database.get_read_session_context() as session:
        
        tenant_id = 1  # Change as needed
        hybrid_manager = HybridProviderManager(session)
        await hybrid_manager.initialize_providers(tenant_id)
        
        result = await hybrid_manager.generate_embeddings(['test local embedding'], tenant_id)
        
        if result.success:
            dimensions = len(result.data[0])
            print(f'✅ Local embeddings working!')
            print(f'📊 Provider: {result.provider_used}')
            print(f'📊 Dimensions: {dimensions}')
            print(f'📊 Expected: 768D for all-mpnet-base-v2')
        else:
            print(f'❌ Local embeddings failed')

asyncio.run(test_local())
"
```

## 🔄 Switch Back to External

To switch back to external embeddings:

```python
# Reverse the activation
cd services/backend-service
python -c "
from app.core.database import get_database
from app.models.unified_models import Integration

database = get_database()
with database.get_write_session_context() as session:
    
    tenant_id = 1  # Change as needed
    
    # Activate external embeddings
    external = session.query(Integration).filter(
        Integration.tenant_id == tenant_id,
        Integration.provider == 'Azure 3-small'
    ).first()
    if external:
        external.active = True
        print(f'✅ Activated external embeddings')

    # Deactivate local embeddings
    local = session.query(Integration).filter(
        Integration.tenant_id == tenant_id,
        Integration.provider == 'MPNet base-v2'
    ).first()
    if local:
        local.active = False
        print(f'❌ Deactivated local embeddings')
    
    session.commit()
    print(f'🎯 Tenant {tenant_id} now using external embeddings')
"
```

## ⚠️ Important Notes

### Vector Compatibility
- **Different models create incompatible vector spaces**
- **Switching models requires re-vectorizing all existing data**
- **768D (local) and 1536D (external) vectors cannot be mixed**
- **No fallback providers**: Only one embedding provider should be active per tenant

### Performance Comparison
| Model | Dimensions | Quality | Cost | Speed |
|-------|------------|---------|------|-------|
| azure-text-embedding-3-small | 1536 | Excellent | $0.73-130/month | Fast |
| all-mpnet-base-v2 | 768 | Very Good | Free | Medium |

### Storage Requirements
- **Model Size**: ~3.6GB
- **Git LFS**: Required for downloading
- **Disk Space**: Ensure sufficient space available

## 🚀 Production Recommendations

1. **Test Thoroughly**: Test local embeddings with your data before switching production
2. **Backup Vectors**: Consider backing up existing vectors before switching
3. **Monitor Performance**: Compare search quality between local and external
4. **Cost Analysis**: Calculate savings vs quality trade-offs
5. **Hybrid Approach**: Use local for development, external for production

## 📞 Support

If you encounter issues:
1. Check model download completed successfully
2. Verify file permissions on model directory
3. Test model loading independently
4. Check database integration configuration
5. Review logs for specific error messages

---

**Current Status**: Azure 3-small active, MPNet base-v2 available but inactive.
**To Switch**: Follow the steps above to activate local embeddings for any tenant.
