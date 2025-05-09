# at the top of routes/user_routes.py
from datetime import datetime, timedelta
import os
import uuid
from dotenv import load_dotenv
from fastapi import APIRouter,BackgroundTasks, Cookie, Depends, HTTPException, Request, Response,status
from sqlalchemy import  func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.user_model import PasswordResetToken,Session, User
from schemas.schemas import ForgotPasswordRequest, LoginRequest, ChangePasswordRequest, ResetPasswordRequest
from service import user_service
from utils.email_utils import send_email
load_dotenv()
FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

auth_router = APIRouter()

@auth_router.post("/login")
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



@auth_router.post("/change-password")
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

@auth_router.post(
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


@auth_router.post("/logout")
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
