import calendar
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from service.user_service import get_db
from service.dashboard_service import compute_avg_duration, get_active_users_by_period, get_sessions

dashboard_router = APIRouter()

@dashboard_router.get("/average-session-length")
async def get_average_session_length(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    this_month = now.month
    this_year = now.year

    # Previous month/year handling
    if this_month == 1:
        prev_month = 12
        prev_year = this_year - 1
    else:
        prev_month = this_month - 1
        prev_year = this_year

    # Fetch sessions (use await!)
    current_sessions = await get_sessions(db, this_year, this_month)
    previous_sessions = await get_sessions(db, prev_year, prev_month)

    # Calculate averages
    current_avg = compute_avg_duration(current_sessions)
    previous_avg = compute_avg_duration(previous_sessions)

    # Change percentage
    if previous_avg == 0:
        change = 100.0 if current_avg > 0 else 0.0
    else:
        change = ((current_avg - previous_avg) / previous_avg) * 100

    minutes = int(current_avg // 60)
    seconds = int(current_avg % 60)

    return {
        "current_month": calendar.month_name[this_month],
        "average_session_length_seconds": current_avg,
        "formatted": f"{minutes}m {seconds}s",
        "percentage_change_vs_last_month": round(change, 2)
    }


@dashboard_router.get("/active-users")
async def active_users(
    granularity: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    db: AsyncSession = Depends(get_db)
):
    return await get_active_users_by_period(db, granularity)


