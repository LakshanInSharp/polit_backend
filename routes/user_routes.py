"""
User management routes for the admin panel.

This module handles user creation, retrieval, updating, deletion,
and current session user inspection. Most routes are admin-only.
"""


from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_model import Role, User, UserDetail
from utils.email.email_utils import send_email
from utils.email import email_templates
from schemas.schemas import AddUser, UserListItem
from service import user_service


load_dotenv()

user_router = APIRouter()


@user_router.post("/admin/add-user", status_code=status.HTTP_201_CREATED)
async def add_user(
    data: AddUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(user_service.get_db),
    current_admin: User = Depends(user_service.admin_required),
) -> dict[str, str]:
    """
    Create a new user (Admin only).

    This endpoint allows an admin to add a new user and sends a temporary password
    to the provided email.
    """
    try:
        user, temp_password = await user_service.create_user(db, data, created_by=current_admin.id)
    except ValueError as ve:
        msg = str(ve).lower()
        if "already exists" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with that email already exists.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request data.")

    background_tasks.add_task(
        user_service.safe_send_email,
        to=data.email,
        subject=email_templates.WELCOME_SUBJECT,
        body=(
            f"Welcome {data.full_name}!\n\n"
            f"Your account has been created with the email: {data.email}\n"
            f"Your temporary password is: {temp_password}\n\n"
            "Please change your password after logging in."
        ),
    )
    return {"msg": f"User '{user.username}' created. Email will be sent shortly."}


@user_router.get(
    "/admin/users",
    response_model=List[UserListItem],
    dependencies=[Depends(user_service.admin_required)],
)
async def list_users(db: AsyncSession = Depends(user_service.get_db)) -> List[UserListItem]:
    """
    Retrieve a list of all users (Admin only).
    """
    q = (
        select(
            User.id.label("id"),
            UserDetail.full_name,
            UserDetail.email,
            Role.name.label("role"),
            User.status,
            User.is_temp_password,
        )
        .join(UserDetail, UserDetail.user_id == User.id)
        .join(Role, User.role_id == Role.id)
    )
    result = await db.execute(q)
    rows = result.all()

    return [
        UserListItem(
            id=id_,
            full_name=fn,
            email=em,
            role=rl,
            status=st,
            is_temp_password=is_temp,
        )
        for id_, fn, em, rl, st, is_temp in rows
    ]


@user_router.delete(
    "/admin/users/{user_id}",
    summary="Delete a user by ID",
    dependencies=[Depends(user_service.admin_required)],
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(user_service.get_db),
) -> dict[str, str]:
    """
    Delete a user by ID (Admin only).
    """
    try:
        deleted = await user_service.delete_user(db, user_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"msg": f"User with ID {user_id} deleted successfully."}


@user_router.put(
    "/admin/users/{user_id}",
    response_model=UserListItem,
    summary="Edit user (full_name, email, role, status)",
)
async def edit_user(
    user_id: int,
    data: AddUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(user_service.get_db),
    current_admin: User = Depends(user_service.admin_required),
) -> UserListItem:
    """
    Update user details (Admin only).

    Allows admins to update a user's full name, email, role, and status.
    If the email is changed or temporary password is reset, emails are sent.
    """
    result = await db.execute(
        select(User, UserDetail)
        .join(UserDetail, User.id == UserDetail.user_id)
        .where(User.id == user_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user, user_detail = row
    old_email = user_detail.email

    try:
        updated, temp_password = await user_service.update_user(
            db=db,
            user_id=user_id,
            data=data,
            modified_by=current_admin.id,
            reset_temp_password=False,
        )
    except ValueError as ve:
        msg = str(ve)
        if "already exists" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with that email already exists."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid update data."
        )

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if old_email != data.email:
        background_tasks.add_task(
            user_service.safe_send_email,
            to=old_email,
            subject=email_templates.EMAIL_UPDATED_SUBJECT,
            body=(
                f"Hello {updated['full_name']},\n\n"
                f"Your account email has been changed to {data.email}.\n"
                "If you did not make this change, please contact support immediately."
            )
        )

    if temp_password:
        background_tasks.add_task(
            user_service.safe_send_email,
            to=data.email,
            subject=email_templates.TEMP_PASSWORD_SUBJECT,
            body=(
                f"Hello {updated['full_name']},\n\n"
                f"Your temporary password has been reset.\n"
                f"Temporary password: {temp_password}\n"
                "Please change it after login."
            )
        )

    if not updated["status"]:
        background_tasks.add_task(
            user_service.safe_send_email,
            to=data.email,
            subject=email_templates.ACCOUNT_DEACTIVATED_SUBJECT,
            body=(
                f"Hello {updated['full_name']},\n\n"
                "Your account has been deactivated. Please contact support if this is unexpected."
            )
        )

    return UserListItem(**updated)


@user_router.get("/me", response_model=UserListItem)
async def read_current_user(current_user: UserListItem = Depends(user_service.get_current_user)) -> UserListItem:
    """
    Get the currently logged-in user's details.
    """
    return current_user
