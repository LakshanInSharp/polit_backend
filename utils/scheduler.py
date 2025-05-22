import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from sqlalchemy import select, and_
from database.db import AsyncSessionLocal, sync_engine
from models.user_model import Session

# 5 days in minutes = 5 * 24 * 60 = 7200
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", str(5 * 24 * 60)))  # default to 7200 minutes
CLEANUP_INTERVAL_MINUTES = int(os.getenv("SESSION_CLEANUP_INTERVAL", "60"))  

async def cleanup_expired_sessions():
    async with AsyncSessionLocal() as db:
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        result = await db.execute(
            select(Session).where(
                and_(
                    Session.start_time < cutoff,
                    Session.end_time.is_(None),
                )
            )
        )
        expired = result.scalars().all()
        for sess in expired:
            sess.end_time = sess.start_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
            db.add(sess)
        if expired:
            await db.commit()

# instantiate the scheduler
jobstores = {
    'default': SQLAlchemyJobStore(engine=sync_engine),
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

scheduler.add_job(
    cleanup_expired_sessions,
    trigger='interval',
    minutes=CLEANUP_INTERVAL_MINUTES,
    id='session_cleanup_job',
    max_instances=1,
    replace_existing=True,
)
