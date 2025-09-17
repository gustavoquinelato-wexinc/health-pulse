# Check what users exist in the database
from app.models.unified_models import User
from app.core.database import get_db_session

session = next(get_db_session())
try:
    users = session.query(User).filter(User.tenant_id == 2).all()  # WEX tenant
    
    print('Users in WEX tenant:')
    for user in users:
        print(f'  Email: {user.email}, Auth Provider: {user.auth_provider}, Active: {user.active}')
        
finally:
    session.close()
