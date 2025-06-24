from datetime import datetime, time, timedelta, timezone
import pytz
from sqlalchemy import and_, distinct, extract, func, or_, select
from models.user_model import Role, Session, User
from sqlalchemy.ext.asyncio import AsyncSession

from models.top_query_gap_doc import TopQueries


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
    colombo_tz = pytz.timezone("Asia/Colombo")
    now = datetime.now(colombo_tz)
    today = now.date()
    results = []

    if granularity == "daily":
        # Hourly breakdown for today (in local time, converted to UTC)
        for hour in range(24):
            local_hour_start = colombo_tz.localize(datetime.combine(today, time(hour, 0)))
            local_hour_end = local_hour_start + timedelta(hours=1)

            hour_start = local_hour_start.astimezone(timezone.utc)
            hour_end = local_hour_end.astimezone(timezone.utc)

            stmt = (
                select(func.count(func.distinct(Session.user_id)))
                .select_from(Session)
                .join(User, User.id == Session.user_id)
                .where(
                    and_(
                        Session.start_time < hour_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= hour_start
                        ),
                        User.role_id == 3
                    )
                )
            )
            
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "period": local_hour_start.strftime("%H:%M"),  # Show in local time
                "active_users": count
            })

    elif granularity == "weekly":
        # Each day of the last 7 days (in local time)
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            local_day_start = colombo_tz.localize(datetime.combine(day, time(0, 0)))
            local_day_end = local_day_start + timedelta(days=1)

            day_start = local_day_start.astimezone(timezone.utc)
            day_end = local_day_end.astimezone(timezone.utc)

            stmt = (
                select(func.count(func.distinct(Session.user_id)))
                .select_from(Session)
                .join(User, User.id == Session.user_id)
                .where(
                    and_(
                        Session.start_time < day_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= day_start
                        ),
                        User.role_id == 3
                    )
                )
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "period": day.strftime("%b %d"),
                "active_users": count
            })

    elif granularity == "monthly":
        # Last 30 days (including today) in local time
        start_day = today - timedelta(days=29)  # 30 days ago
        for i in range(30):
            day = start_day + timedelta(days=i)
            local_day_start = colombo_tz.localize(datetime.combine(day, time(0, 0)))
            local_day_end = local_day_start + timedelta(days=1)

            day_start = local_day_start.astimezone(timezone.utc)
            day_end = local_day_end.astimezone(timezone.utc)

            stmt = (
                select(func.count(func.distinct(Session.user_id)))
                .select_from(Session)
                .join(User, User.id == Session.user_id)
                .where(
                    and_(
                        Session.start_time < day_end,
                        or_(
                            Session.end_time == None,
                            Session.end_time >= day_start
                        ),
                        User.role_id == 3
                    )
                )
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            results.append({
                "period": day.strftime("%b %d"),  # e.g., 'May 04'
                "active_users": count
            })

    return results



async def get_avg_searches_per_user(db: AsyncSession):
    total_searches_stmt = select(func.sum(TopQueries.count))
    unique_users_stmt = select(func.count(func.distinct(TopQueries.user_id)))

    total_result = await db.execute(total_searches_stmt)
    user_result = await db.execute(unique_users_stmt)

    total_searches = total_result.scalar() or 0
    unique_users = user_result.scalar() or 1  # avoid division by zero

    average = total_searches / unique_users
    return average

def serialize_query(q):
    data = q.model_dump()
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    return data

def clean_query_dict(q: dict) -> dict:
    q = q.copy()
    # Ensure page_no is a string without curly braces or remove it if not needed
    if 'page_no' in q:
        # Option 1: Remove page_no entirely if not used
        del q['page_no']
        # Option 2: Or sanitize page_no, e.g.:
        # q['page_no'] = str(q['page_no']).replace("{", "").replace("}", "")
    return q


