from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, distinct, extract, func, or_, select
from models.user_model import Role, Session, User
from sqlalchemy.ext.asyncio import AsyncSession


async def get_sessions(db, year, month):
    result = await db.execute(
        select(Session)
        .join(User, Session.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .filter(Role.name != "admin")
        .filter(Session.end_time.isnot(None))
        .filter(extract("year", Session.start_time) == year)
        .filter(extract("month", Session.start_time) == month)
    )
    return result.scalars().all()

def compute_avg_duration(sessions):
    if not sessions:
        return 0
    return sum([(s.end_time - s.start_time).total_seconds() for s in sessions]) / len(sessions)




async def get_active_users_by_period(db: AsyncSession, granularity: str = "daily"):
    now = datetime.now(timezone.utc)
    today = now.date()
    results = []

    if granularity == "daily":
        # Hourly breakdown for today
        for hour in range(24):
            hour_start = datetime.combine(today, datetime.min.time()).replace(hour=hour)
            hour_end = hour_start + timedelta(hours=1)

            stmt = (
                select(func.count(distinct(Session.user_id)))
                .where(
                    and_(
                        Session.start_time < hour_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= hour_start
                        )
                    )
                )
            )
            
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "day": hour_start.strftime("%H:%M"),  # e.g., "14:00"
                "active_users": count
            })

    elif granularity == "weekly":
        # Each day of the last 7 days
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            stmt = (
                select(func.count(distinct(Session.user_id)))
                .where(
                    and_(
                        Session.start_time < day_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= day_start
                        )
                    )
                )
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "day": day.strftime("%b %d"),  # e.g., "May 14"
                "active_users": count
            })

    elif granularity == "monthly":
        # All days from the beginning of the month until today
        first_day_of_month = today.replace(day=1)
        num_days = (today - first_day_of_month).days + 1

        for i in range(num_days):
            day = first_day_of_month + timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            stmt = (
                select(func.count(distinct(Session.user_id)))
                .where(
                    and_(
                        Session.start_time < day_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= day_start
                        )
                    )
                )
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "day": day.strftime("%b %d"),  # e.g., "May 01"
                "active_users": count
            })

    return results