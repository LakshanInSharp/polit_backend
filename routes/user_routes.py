# at the top of routes/user_routes.py
from datetime import datetime, timedelta
import os
from typing import List
import uuid
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response,status
from sqlalchemy import  func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.db import SessionLocal
from models import user_model
from models.user_model import PasswordResetToken, Role, Session, User, UserDetail
from schemas.schemas import ForgotPasswordRequest, LoginRequest, ChangePasswordRequest, AddUser, ResetPasswordRequest, UserListItem
from service import user_service
from utils.email_utils import send_email
load_dotenv()
FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

router = APIRouter()


@router.post("/admin/add-user")
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


@router.get("/admin/users", response_model=List[UserListItem])
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


@router.put( "/admin/users/{user_id}",
    response_model=UserListItem,
    summary="Edit an existing user (full_name, email, role, status)"
)
async def edit_user(
    user_id: int,
    data: AddUser,
    db: AsyncSession = Depends(user_service.get_db),
):
    updated = await user_service.update_user(db, user_id, data, modified_by=1)
    if not updated:
        raise HTTPException(404, "User not found")
    return updated


@router.post("/login")
async def login(
    req: LoginRequest, response: Response, db: AsyncSession = Depends(user_service.get_db)
):
    # Attempt to find the user in the database
    user = await user_service.login_user(db, req.username, req.password)
    
    # If user not found or password incorrect, raise detailed error
    if not user:
        raise HTTPException(401, detail="Invalid credentials")

    # Create session & set cookie
    uuid = await user_service.create_session(db, user["id"])
    response.set_cookie("session_uuid", uuid, httponly=True, secure=True, samesite="Lax")

    # If it's a temporary password, force a password change
    if user["is_temp_password"]:
        return {
            "msg": "Login successful, please change your password.",
            "redirect_to_change_password": True  # <-- Flag for frontend to handle redirect
        }

    return {
        "msg": "Login successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "is_temp_password": user["is_temp_password"]
        }
    }



@router.post("/change-password")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(user_service.get_db)
):
    # 1️⃣ Authenticate session
    session_uuid = request.cookies.get("session_uuid")
    if not session_uuid:
        raise HTTPException(401, "Not authenticated")

    result = await db.execute(
        select(Session).filter_by(session_uuid=session_uuid)
    )
    sess = result.scalar_one_or_none()
    if not sess or not sess.user_id:
        raise HTTPException(401, "Invalid session")

    # Load the user
    result = await db.execute(select(User).filter_by(id=sess.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # Verify old (temporary) password
    if not user_service.verify_password(data.old_password, user.password_hash):
        raise HTTPException(400, "Old (temporary) password is incorrect")

    # Validate new vs. confirm
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "New passwords do not match")

    # Hash & save new password
    user.password_hash = user_service.hash_password(data.new_password)
    user.is_temp_password = False
    await db.commit()

    return {"message": "Password changed successfully"}


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request a password-reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(user_service.get_db),
):
    # 1. Find user by email
    result = await db.execute(
        select(User).where(User.user_detail.has(email=payload.email))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # 2. Generate & store token
    token = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(hours=1)

    reset_record = PasswordResetToken(
        user_id=user.id, token=token, expiration=expiry
    )
    db.add(reset_record)
    await db.commit()

    # 3. Build reset URL
    reset_url = f"{FRONTEND_BASE}/reset-password?token={token}"

    # 4. Send email with link
    background_tasks.add_task(
        send_email,
        payload.email,
        "[Polit] Password Reset Request",
        (
            f"Hello,\n\n"
            "We received a request to reset your password. "
            "Click the link below to set a new password:\n\n"
            f"{reset_url}\n\n"
            "If you didn’t request this, you can ignore this email.\n\n"
            "— Polit App Team"
        ),
    )

    return {"message": "Password reset email sent"}

@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(user_service.get_db),
):
    # 1. Lookup token record (and eager-load User)
    stmt = (
        select(PasswordResetToken)
        .where(PasswordResetToken.token == payload.token)
        .options()
    )
    result = await db.execute(stmt)
    reset_rec = result.scalar_one_or_none()

    if not reset_rec:
        raise HTTPException(400, "Invalid reset token")
    if reset_rec.expiration < datetime.utcnow():
        # token expired
        # clean up expired token
        await db.delete(reset_rec)
        await db.commit()
        raise HTTPException(400, "Reset token has expired")

    # 2. Update user’s password
    user = await db.get(User, reset_rec.user_id)
    user.password_hash = user_service.hash_password(payload.new_password)
    user.is_temp_password = False

    # 3. Delete token record
    await db.delete(reset_rec)
    await db.commit()

    return {"message": "Password successfully reset"}



@router.get("/me", response_model=UserListItem)
async def read_current_user(current_user: UserListItem = Depends(user_service.get_current_user)):
    """
    Returns the currently logged-in user based on the `session_uuid` cookie.
    """
    return {**current_user.dict(), "is_temp_password": current_user.is_temp_password}


@router.post("/logout")
async def logout(
    response: Response,
    session_uuid: str | None = Cookie(default=None, alias="session_uuid"),
    db: AsyncSession = Depends(user_service.get_db),
):
    if session_uuid:
        await db.execute(
            update(Session)
            .where(Session.session_uuid == session_uuid, Session.end_time.is_(None))
            .values(end_time=func.now())
        )
        await db.commit()
        response.delete_cookie("session_uuid")
    return {"msg": "Logged out"}
