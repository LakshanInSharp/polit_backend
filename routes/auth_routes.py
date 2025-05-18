from datetime import datetime, timedelta, timezone
import os
import uuid

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_model import PasswordResetToken,  Session, User
from schemas.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
)
from service import user_service
from utils.email.email_utils import send_email

load_dotenv()
FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

auth_router = APIRouter()


@auth_router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(user_service.get_db)
):
    """
    Authenticate user and create a new session.

    Args:
        req (LoginRequest): Login credentials (username and password).
        response (Response): FastAPI response object to set cookies.
        db (AsyncSession): Database session dependency.

    Returns:
        dict: Message about login status and user info or redirect instruction.
    Raises:
        HTTPException: If credentials are invalid.
    """
    user = await user_service.login_user(db, req.username, req.password)
    if not user:
        raise HTTPException(401, detail="Invalid credentials")

    session_uuid = await user_service.create_session(db, user["id"])
    response.set_cookie(
        "session_uuid",
        session_uuid,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=int(timedelta(days=5).total_seconds())
    )

    if user["is_temp_password"]:
        return {
            "msg": "Login successful, please change your password.",
            "redirect_to_change_password": True
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


@auth_router.post("/change-password")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(user_service.get_db)
):
    """
    Change the password for the authenticated user.

    Args:
        request (Request): FastAPI request object to access cookies.
        data (ChangePasswordRequest): Old password, new password, and confirmation.
        db (AsyncSession): Database session dependency.

    Returns:
        dict: Success message on password change.

    Raises:
        HTTPException: If user is not authenticated, old password is incorrect,
                       new passwords do not match, or user/session is invalid.
    """
    session_uuid = request.cookies.get("session_uuid")
    if not session_uuid:
        raise HTTPException(401, "Not authenticated")

    result = await db.execute(
        select(Session).where(Session.session_uuid == session_uuid, Session.end_time.is_(None))
    )
    sess = result.scalar_one_or_none()
    if not sess or not sess.user_id:
        raise HTTPException(401, "Invalid session")

    user = await db.get(User, sess.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if not user_service.verify_password(data.old_password, user.password_hash):
        raise HTTPException(400, "Old password is incorrect")
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "New passwords do not match")

    user.password_hash = user_service.hash_password(data.new_password)
    user.is_temp_password = False


    utc_now = datetime.now(timezone.utc)
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.end_time.is_(None))
        .values(end_time=utc_now)
    )

    await db.commit()

    return {"message": "Password changed successfully"}


@auth_router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request a password-reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(user_service.get_db),
):
    """
    Generate a password reset token and send reset email.

    Args:
        payload (ForgotPasswordRequest): User email for password reset.
        background_tasks (BackgroundTasks): FastAPI background tasks to send email.
        db (AsyncSession): Database session dependency.

    Returns:
        dict: Message indicating password reset email was sent.

    Raises:
        HTTPException: If user with given email does not exist.
    """
    result = await db.execute(
        select(User).where(User.user_detail.has(email=payload.email))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    token = str(uuid.uuid4())
    utc_now = datetime.now(timezone.utc)
    expiration = utc_now + timedelta(hours=1)
    await db.execute(
        PasswordResetToken.__table__.insert().values(
            user_id=user.id,
            token=token,
            expiration=expiration
        )
    )
    await db.commit()

    reset_url = f"{FRONTEND_BASE}/reset-password?token={token}"
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


@auth_router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(user_service.get_db),
):
    """
    Reset user password given a valid reset token.

    Args:
        payload (ResetPasswordRequest): Reset token and new password.
        db (AsyncSession): Database session dependency.

    Returns:
        dict: Success message on password reset.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    stmt = select(PasswordResetToken).where(PasswordResetToken.token == payload.token)
    result = await db.execute(stmt)
    reset_rec = result.scalar_one_or_none()

    utc_now = datetime.now(timezone.utc)

    if not reset_rec:
        raise HTTPException(400, "Invalid reset token")
    if reset_rec.expiration < utc_now:
        await db.delete(reset_rec)
        await db.commit()
        raise HTTPException(400, "Reset token has expired")

    user = await db.get(User, reset_rec.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.password_hash = user_service.hash_password(payload.new_password)
    user.is_temp_password = False


    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.end_time.is_(None))
        .values(end_time=utc_now)
    )

    await db.delete(reset_rec)
    await db.commit()

    return {"message": "Password successfully reset"}


@auth_router.post("/logout")
async def logout(
    response: Response,
    session_uuid: str | None = Cookie(default=None, alias="session_uuid"),
    db: AsyncSession = Depends(user_service.get_db),
):
    """
    Logout user by ending the current session and deleting the session cookie.

    Args:
        response (Response): FastAPI response object to delete cookies.
        session_uuid (str | None): Session UUID cookie.
        db (AsyncSession): Database session dependency.

    Returns:
        dict: Confirmation message for logout.

    Raises:
        HTTPException: If user is not authenticated (no session cookie).
    """
    if not session_uuid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    
    utc_now = datetime.now(timezone.utc)
    await db.execute(
        update(Session)
        .where(Session.session_uuid == session_uuid, Session.end_time.is_(None))
        .values(end_time=utc_now)
    )
    await db.commit()

    response.delete_cookie("session_uuid")

    return {"msg": "Logged out"}
