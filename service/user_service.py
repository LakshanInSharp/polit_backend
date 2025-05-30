# Standard Library
import os
import random
import secrets
import string
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Cookie, status
from passlib.hash import pbkdf2_sha256
from sqlalchemy import func, select, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from asyncpg import UniqueViolationError


from database.db import AsyncSessionLocal
from models import user_model
from models.user_model import Role, User, UserDetail, Session
from schemas.user_schema import AddUser, UserListItem
from utils.email.email_utils import send_email




# ================================
# Database Session Utilities
# ================================
async def get_db():
    """
    Provides an async database session.
    Yields:
        AsyncSession: An asynchronous SQLAlchemy database session.    
    """
    async with AsyncSessionLocal() as db:
        yield db


# ================================
# Authenication & Authorization
# ================================

async def get_current_user(
    session_uuid: str | None = Cookie(default=None, alias="session_uuid"),
    db: AsyncSession = Depends(get_db),
) -> UserListItem:
    if not session_uuid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    q_sess = select(Session).where(
        and_(
            Session.session_uuid == session_uuid,
            Session.end_time == None
        )
    )
    res = await db.execute(q_sess)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # EXPIRATION CHECK: session older than 5 days 
    now = datetime.now(timezone.utc)
    session_age = now - sess.start_time
    if session_age > timedelta(days=5):
        sess.end_time = now
        await db.commit()
        raise HTTPException(status_code=401, detail="Session expired")


    q_user = (
        select(
            User.id.label("id"),
            UserDetail.full_name,
            UserDetail.email,
            Role.name.label("role"),
            User.status.label("status"),
            User.is_temp_password,
        )
        .join(UserDetail, UserDetail.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .where(User.id == sess.user_id)
    )
    row = (await db.execute(q_user)).first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    id_, fn, em, rl, st, tp = row

    return UserListItem(
        id=id_,
        full_name=fn,
        email=em,
        role=rl,
        status=st,
        is_temp_password=tp
    )


async def admin_required(current_user: User = Depends(get_current_user)):
    """
    Dependency to enforce that the current user is an admin.
    Raises HTTP 403 if not admin.
    """
    if not current_user.role or current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )
    return current_user




async def login_user(db, username: str, password: str) -> dict:
    """
    Authenticates a user with username and password.

    Args:
        db (AsyncSession): Database session.
        username (str): Email/username.
        password (str): Plain text password.

    Returns:
        dict: User information if authenticated.

    Raises:
        HTTPException: If the user is inactive.
    """
    row = await db.execute(
        select(User, Role.name)
        .join(Role, User.role_id == Role.id)
        .where(User.username == username)
    )
    entry = row.first()
    if not entry:
        return None

    user, role_name = entry

 
    if not user.status:
        raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Account is inactive. Contact administrator."
    )

    if not verify_password(password, user.password_hash):
        return None

   
    await db.commit()

    return {
        "id": user.id,
        "username": user.username,
        "role": role_name,
        "is_temp_password": user.is_temp_password,
    }




# ================================
# Password Management
# ================================



def generate_temp_password() -> str:
    """
    Generates a secure temporary password.

    Returns:
        str: A secure random string.
    """
    return secrets.token_urlsafe(8)

def hash_password(password: str) -> str:
    """
    Hashes a plain password using PBKDF2.

    Args:
        password (str): The plain text password.

    Returns:
        str: The hashed password.
    """
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies a password against its hashed value.

    Args:
        password (str): Plain text password.
        hashed (str): Hashed password.

    Returns:
        bool: True if the password matches, False otherwise.
    """

    return pbkdf2_sha256.verify(password, hashed)




# ================================
# User Management
# ================================



async def email_exists_for_other_user(db: AsyncSession, email: str, exclude_user_id: int) -> bool:
    result = await db.execute(
        select(User).where(User.username == email, User.id != exclude_user_id)
    )
    return result.scalar_one_or_none() is not None



async def create_initial_admin_if_needed(db: AsyncSession):
    """
    Creates an initial admin user if no admin exists.

    Args:
        db (AsyncSession): Database session.

    Returns:
        User: The created or existing admin user.
    """
   
    query = select(User).where(User.role_id == 1) 
    result = await db.execute(query)
    existing_admin = result.scalars().all()

    if existing_admin:
        return existing_admin[0]

    
    temp_password = generate_temp_password() 
    hashed_password = hash_password(temp_password)


    admin_email = os.getenv("ADMIN_EMAIL")
    admin_full_name = os.getenv("ADMIN_FULL_NAME")
    
    if not admin_email or not admin_full_name:
        raise ValueError("ADMIN_EMAIL and ADMIN_FULL_NAME must be set in environment variables")


    user_data = User(
        username=admin_email,
        password_hash=hashed_password,
        role_id=1,  
        is_temp_password=True,
        created_by=0  
    )

   
    db.add(user_data)
    await db.commit()
    await db.refresh(user_data)


    user_detail = UserDetail(
        user_id=user_data.id,
        full_name=admin_full_name,
        email=admin_email
    )

    db.add(user_detail)
    await db.commit()


    await send_email(
        to=user_data.username,
        subject="Your Initial Admin Account",
        body=f"Welcome! Your temporary password is: {temp_password}. Please change it after logging in."
    )
    
    return user_data



async def get_role_id(db: AsyncSession, role_name: str) -> int:
    """
    Fetches the role ID based on role name.

    Args:
        db (AsyncSession): Database session.
        role_name (str): Role name string.

    Returns:
        int: Role ID.

    Raises:
        ValueError: If the role does not exist.
    """
    q = await db.execute(select(Role).where(Role.name == role_name))
    role = q.scalar_one_or_none()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")
    return role.id


    
async def create_user(db: AsyncSession, data: AddUser, created_by: int):
    """
    Creates a new user with temporary password and user detail.

    Args:
        db (AsyncSession): Database session.
        data (AddUser): User creation input.
        created_by (int): ID of the creator.

    Returns:
        tuple[User, str]: The created user and the temporary password.

    Raises:
        ValueError: If the email is already taken.
    """
    temp_password = generate_temp_password()
    hashed_password = hash_password(temp_password)
    role_id = await get_role_id(db, data.role)


    user = User(
        username=data.email,
        password_hash=hashed_password,
        role_id=role_id,
        created_by=created_by,
        is_temp_password=True,
        status=data.status,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()

        if isinstance(e.orig, UniqueViolationError) or "duplicate key value violates unique constraint" in str(e.orig).lower():
            raise ValueError("A user with that email already exists.")
        raise
    await db.refresh(user)

    detail = UserDetail(
        user_id=user.id,
        email=data.email,
        full_name=data.full_name
    )
    db.add(detail)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, UniqueViolationError) or "duplicate key value violates unique constraint" in str(e.orig).lower():
            raise ValueError("A user with that email already exists.")
        raise
    await db.refresh(detail)

    return user, temp_password




async def update_user(
    db: AsyncSession,
    user_id: int,
    data: AddUser,
    modified_by: int,
    reset_temp_password: bool = False,
) -> tuple[dict, str | None] | None:
    """
    Updates an existing user and their detail record.

    Args:
        db (AsyncSession): Database session.
        user_id (int): ID of the user to update.
        data (AddUser): New user data.
        modified_by (int): ID of the admin making changes.
        reset_temp_password (bool): Whether to reset password.

    Returns:
        tuple[dict, str | None] | None: Updated user info and optional new password.
    """
 
    user = await db.get(User, user_id)
    detail = (
        await db.execute(select(UserDetail).where(UserDetail.user_id == user_id))
    ).scalar_one_or_none()

  
    if not user or not detail:
        return None

    if await email_exists_for_other_user(db, data.email, user_id):
        raise ValueError("A user with that email already exists.")

    email_changed = user.username != data.email

    detail.full_name = data.full_name
    detail.email = data.email
    user.username = data.email
    user.status = data.status
    detail.status = data.status  


    role = (
        await db.execute(select(Role).where(Role.name == data.role))
    ).scalar_one_or_none()
    if not role:
        raise ValueError(f"Role '{data.role}' not found")
    user.role_id = role.id

    temp_password = None
   
    if email_changed or reset_temp_password:
        temp_password = generate_temp_password()
        user.password_hash = hash_password(temp_password)
        user.is_temp_password = True


    if email_changed or not user.status:
        await db.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.end_time.is_(None))
            .values(end_time=datetime.now(timezone.utc))
        )

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        orig = getattr(e, "orig", None)
        if isinstance(orig, UniqueViolationError) or getattr(orig, "sqlstate", "") == "23505":
            raise ValueError("A user with that email already exists.")
        raise ValueError("Failed to update user.") from e

    await db.refresh(user)
    await db.refresh(detail)


    return {
        "id": user.id,
        "full_name": detail.full_name,
        "email": detail.email,
        "role": role.name,
        "status": user.status,
        "is_temp_password": user.is_temp_password,
    }, temp_password



async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """
    Deletes a user and their associated detail record.

    Args:
        db (AsyncSession): Database session.
        user_id (int): ID of the user to delete.

    Returns:
        bool: True if deleted, False if not found.
    """

    user = await db.get(User, user_id)
    if not user:
        return False

    detail = await db.execute(
        select(UserDetail).where(UserDetail.user_id == user_id)
    )
    detail_obj = detail.scalar_one_or_none()
    if detail_obj:
        await db.delete(detail_obj)

    await db.delete(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise

    return True




# ================================
# Session Management
# ================================



async def create_session(db: AsyncSession, user_id: int):
    session_uuid = str(uuid4())
    sess = Session(user_id=user_id, session_uuid=session_uuid)
    db.add(sess)
    await db.commit()
    return session_uuid


async def end_session(db: AsyncSession, uuid: str):
    q = await db.execute(select(Session).where(Session.session_uuid == uuid))
    sess = q.scalar_one_or_none()
    if sess:
        sess.end_time = datetime.now(timezone.utc)
        await db.commit()




# ================================
# Email & Token Utilities
# ================================


def generate_token(length=6):
    """
    Generates a random alphanumeric token for reset.

    Args:
        length (int): Length of the token. Default is 6.

    Returns:
        str: The generated token.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


async def send_reset_email(to_email: str, reset_token: str) -> None:
    """
    Sends a password reset token via email using the send_email function.

    Args:
        to_email (str): Recipient email.
        reset_token (str): The token to include in the email body.
    """
    subject = "Password Reset Request"
    body = f"Here is your reset token: {reset_token}"

    await send_email(to_email, subject, body)




async def safe_send_email(*args, **kwargs):
    """Wrapper for send_email with exception handling; silently ignores exceptions."""
    try:
        await send_email(*args, **kwargs)
    except Exception:
     
        pass


