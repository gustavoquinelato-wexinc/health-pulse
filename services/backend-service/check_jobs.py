# Check job names in database to ensure consistency
from app.models.unified_models import JobSchedule
from app.core.database import get_db_session

session = next(get_db_session())
try:
    jobs = session.query(JobSchedule).filter(
        JobSchedule.tenant_id == 2,  # WEX tenant
        JobSchedule.active == True
    ).order_by(JobSchedule.execution_order).all()
    
    print('Current job names in database:')
    for job in jobs:
        print(f'  "{job.job_name}" - Status: {job.status} (Order: {job.execution_order})')
        
finally:
    session.close()
