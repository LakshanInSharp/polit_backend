import asyncio
import calendar
import logging
from typing import List
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from database.db import AsyncSessionLocal
from schemas.domaingaps_schema import DomainGap
from service.user_service import get_db
from service.dashboard_service import compute_avg_duration, get_active_users_by_period, get_sessions, serialize_query
from schemas.querycounts_schema import QueryCount, FileCount
from utils.websocket_manager import manager

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

dashboard_router = APIRouter()

@dashboard_router.get("/average-session-length")
async def get_average_session_length(db: AsyncSession = Depends(get_db)):
    logger.info("Calculating average session length...")

    now = datetime.now(timezone.utc)
    this_month = now.month
    this_year = now.year
    logger.info(f"Current date: {this_year}-{this_month}")

    if this_month == 1:
        prev_month = 12
        prev_year = this_year - 1
    else:
        prev_month = this_month - 1
        prev_year = this_year

    logger.info(f"Fetching sessions for current month: {this_year}-{this_month}")
    current_sessions = await get_sessions(db, this_year, this_month)
    logger.info(f"Fetched {len(current_sessions)} sessions for current month")

    logger.info(f"Fetching sessions for previous month: {prev_year}-{prev_month}")
    previous_sessions = await get_sessions(db, prev_year, prev_month)
    logger.info(f"Fetched {len(previous_sessions)} sessions for previous month")

    current_avg = compute_avg_duration(current_sessions)
    previous_avg = compute_avg_duration(previous_sessions)

    logger.info(f"Current average session duration: {current_avg} seconds")
    logger.info(f"Previous average session duration: {previous_avg} seconds")

    if previous_avg == 0:
        change = 100.0 if current_avg > 0 else 0.0
    else:
        change = ((current_avg - previous_avg) / previous_avg) * 100

    minutes = int(current_avg // 60)
    seconds = int(current_avg % 60)

    logger.info("Average session length calculated successfully")

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
    logger.info(f"Getting active users with granularity: {granularity}")
    data = await get_active_users_by_period(db, granularity)
    logger.info(f"Retrieved active users data for granularity: {granularity}")
    return data


@dashboard_router.get("/top-queries", response_model=List[QueryCount])
async def get_top_queries(db: AsyncSession = Depends(get_db)):
    logger.info("Querying top queries from 'top_queries' table")
    query = text("SELECT source, topic, count FROM top_queries ORDER BY count DESC")
    result = await db.execute(query)
    rows = result.fetchall()
    logger.info(f"Retrieved {len(rows)} top queries")
    return [
        QueryCount(
            source=row[0],
            main_topic=row[1],
            count=row[2]
        ) for row in rows
    ]


@dashboard_router.get("/gap-in-queries", response_model=List[DomainGap])
async def get_gap_queries(db: AsyncSession = Depends(get_db)):
    logger.info("Querying gap-in-queries from 'gap_in_document_count'")
    query = text("""
        SELECT main_topic, SUM(count) AS total_count 
        FROM gap_in_document_count
        GROUP BY main_topic 
        ORDER BY total_count DESC
    """)
    result = await db.execute(query)
    rows = result.fetchall()
    logger.info(f"Retrieved {len(rows)} gap-in-query records")
    return [
        DomainGap(
            main_topic=row[0],
            count=row[1]
        ) for row in rows
    ]


@dashboard_router.get("/most_referenced_file", response_model=List[FileCount])
async def get_most_referenced_file(db: AsyncSession = Depends(get_db)):
    logger.info("Querying most referenced files from 'top_queries'")
    query = text("""
        SELECT LOWER(TRIM(source)) AS source, SUM(count) AS total_count 
        FROM top_queries 
        GROUP BY LOWER(TRIM(source)) 
        ORDER BY total_count DESC
    """)
    result = await db.execute(query)
    rows = result.fetchall()
    logger.info(f"Retrieved {len(rows)} most referenced files")
    return [
        FileCount(
            source=row[0],
            count=row[1],
        ) for row in rows
    ]


@dashboard_router.websocket("/ws/average-session-length")
async def websocket_avg_session_length(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            now = datetime.now(timezone.utc)
            this_month = now.month
            this_year = now.year
            if this_month == 1:
                prev_month = 12
                prev_year = this_year - 1
            else:
                prev_month = this_month - 1
                prev_year = this_year

            async with AsyncSessionLocal() as db:
                current_sessions = await get_sessions(db, this_year, this_month)
                previous_sessions = await get_sessions(db, prev_year, prev_month)

            current_avg = compute_avg_duration(current_sessions)
            previous_avg = compute_avg_duration(previous_sessions)

            if previous_avg == 0:
                change = 100.0 if current_avg > 0 else 0.0
            else:
                change = ((current_avg - previous_avg) / previous_avg) * 100

            minutes = int(current_avg // 60)
            seconds = int(current_avg % 60)

            result = {
                "current_month": calendar.month_name[this_month],
                "average_session_length_seconds": current_avg,
                "formatted": f"{minutes}m {seconds}s",
                "percentage_change_vs_last_month": round(change, 2)
            }

            await websocket.send_json(result)

            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=5)
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@dashboard_router.websocket("/ws/active-users")
async def websocket_active_users(websocket: WebSocket):
    await manager.connect(websocket)
    granularity = "daily"  # or param-driven if you want
    try:
        while True:
            async with AsyncSessionLocal() as db:
                data = await get_active_users_by_period(db, granularity)

            await websocket.send_json({"granularity": granularity, "data": data})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@dashboard_router.websocket("/ws/gap-in-queries")
async def websocket_gap_queries(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async with AsyncSessionLocal() as db:
                query = text("""
                    SELECT main_topic, SUM(count) AS total_count 
                    FROM gap_in_document_count
                    GROUP BY main_topic 
                    ORDER BY total_count DESC
                """)
                result = await db.execute(query)
                rows = result.fetchall()

            response = [
                DomainGap(main_topic=row[0], count=row[1])
                for row in rows
            ]

            await websocket.send_json([g.dict() for g in response])
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@dashboard_router.websocket("/ws/most_referenced_files")
async def websocket_most_referenced_file(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async with AsyncSessionLocal() as db:
                query = text("""
                    SELECT LOWER(TRIM(source)) AS source, SUM(count) AS total_count 
                    FROM top_queries 
                    GROUP BY LOWER(TRIM(source)) 
                    ORDER BY total_count DESC
                """)
                result = await db.execute(query)
                rows = result.fetchall()

            response = [
                FileCount(source=row[0], count=row[1])
                for row in rows
            ]

            await websocket.send_json([f.dict() for f in response])
            await asyncio.sleep(100)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@dashboard_router.websocket("/ws/top-queries")
async def websocket_top_queries(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            async with AsyncSessionLocal() as db:
                query = text("SELECT source, topic, count FROM top_queries ORDER BY count DESC")
                result = await db.execute(query)
                rows = result.fetchall()

            response = [
                QueryCount(
                    source=row[0],
          
                    main_topic=row[1],
                    count=row[2]
                )
                for row in rows
            ]

            await websocket.send_json([q.dict() for q in response])
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)