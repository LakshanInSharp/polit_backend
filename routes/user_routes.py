# at the top of routes/user_routes.py
import os
from typing import List
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import  select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user_model import Role, User, UserDetail
from schemas.schemas import  AddUser, UserListItem
from service import user_service
from utils.email_utils import send_email
load_dotenv()
FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

user_router = APIRouter()


@user_router.post("/admin/add-user")

async def add_user(
    data: AddUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(user_service.get_db)
):
        # Ensure initial admin exists
    initial_admin = await user_service.create_initial_admin_if_needed(db)
    created_by = initial_admin.id
    try:
        user, temp_password = await user_service.create_user(db, data, created_by)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    # Send email in the background
    background_tasks.add_task(
        send_email,
        to=data.email,
        subject="[Polit] Welcome — Your Temporary Credentials",
        body=(
            f"Hello {data.full_name},\n\n"
            "An administrator has created an account for you.\n\n"
            f"Username: {data.email}\n"
            f"Temporary password: {temp_password}\n\n"
            "Please log in and change your password immediately.\n\n"
            "— Polit App Team"
        ),
    )

    return {"msg": f"User '{user.username}' created. Email will be sent shortly."}


@user_router.get("/admin/users", response_model=List[UserListItem])
async def list_users(db: AsyncSession = Depends(user_service.get_db)):
    q = (
        select(
            User.id.label("id"),
            UserDetail.full_name,
            UserDetail.email,
            Role.name.label("role"),
            UserDetail.status,
            User.is_temp_password,  # Ensure this field is selected
        )
        .join(UserDetail, UserDetail.user_id == User.id)
        .join(Role, User.role_id == Role.id)
    )
    result = await db.execute(q)
    rows = result.all()  # List of tuples

    return [
        {
            "id": id_,
            "full_name": fn,
            "email": em,
            "role": rl,
            "status": st,
            "is_temp_password": is_temp,  # Ensure this field is included in the response
        }
        for id_, fn, em, rl, st, is_temp in rows
    ]


@user_router.put(
    "/admin/users/{user_id}",
    response_model=UserListItem,
    summary="Edit an existing user (full_name, email is immutable, role, status)"
)
async def edit_user(
    user_id: int,
    data: AddUser,
    db: AsyncSession = Depends(user_service.get_db),
):
    try:
        updated = await user_service.update_user(db, user_id, data, modified_by=1)
    except ValueError as ve:
        # This catches any role‐not‐found or integrity errors
        raise HTTPException(status_code=400, detail=str(ve))

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return updated

@user_router.get("/me", response_model=UserListItem)
async def read_current_user(current_user: UserListItem = Depends(user_service.get_current_user)):
    """
    Returns the currently logged-in user based on the `session_uuid` cookie.
    """
    return {**current_user.dict(), "is_temp_password": current_user.is_temp_password}


