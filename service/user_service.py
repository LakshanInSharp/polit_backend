from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import random
import secrets
import smtplib
import string
from uuid import uuid4
from fastapi import Depends, HTTPException, Cookie
from passlib.hash import pbkdf2_sha256
from sqlalchemy import func, select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import AsyncSessionLocal
from models import user_model
from models.user_model import Role, User, UserDetail, Session
from schemas.schemas import AddUser, UserListItem
from utils.email_utils import send_email

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db

def generate_temp_password() -> str:
    return secrets.token_urlsafe(8)

def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pbkdf2_sha256.verify(password, hashed)

async def create_initial_admin_if_needed(db: AsyncSession):
    # Check if an admin already exists in the system
    query = select(User).where(User.role_id == 1)  # Assuming role_id=1 is 'admin'
    result = await db.execute(query)
    existing_admin = result.scalars().all()

    if existing_admin:
        # If an admin exists, return the first one
        return existing_admin[0]

    # If no admin exists, create the initial admin with a random password
    temp_password = generate_temp_password()  # Generate a secure random temporary password
    hashed_password = hash_password(temp_password)


     # Get admin email and full name from environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_full_name = os.getenv("ADMIN_FULL_NAME")
    
    # Create user data for the initial admin
    user_data = User(
        username=admin_email,
        password_hash=hashed_password,
        role_id=1,  # Admin role
        is_temp_password=True,
        created_by=0  # System-created
    )

    # Add the user to the session and commit
    db.add(user_data)
    await db.commit()
    await db.refresh(user_data)

    # Create the corresponding user detail (for full_name and email)
    user_detail = UserDetail(
        user_id=user_data.id,
        full_name=admin_full_name,
        email=admin_email
    )

    db.add(user_detail)
    await db.commit()

    # Send the temporary password to the admin via email
    await send_email(
        to=user_data.username,
        subject="Your Initial Admin Account",
        body=f"Welcome! Your temporary password is: {temp_password}. Please change it after logging in."
    )
    
    return user_data



async def get_role_id(db: AsyncSession, role_name: str) -> int:
    q = await db.execute(select(Role).where(Role.name == role_name))
    role = q.scalar_one_or_none()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")
    return role.id



async def create_user(db: AsyncSession, data: AddUser, created_by: int):
    # Generate a temporary password and hash it
    temp_password = generate_temp_password()  
    hashed_password = hash_password(temp_password)

    # Assign the role based on the provided role name
    role_id = await get_role_id(db, data.role)

    # Create the user with a hashed temporary password
    user = User(
        username=data.email,
        password_hash=hashed_password,
        role_id=role_id,
        created_by=created_by,
        is_temp_password=True,  # Mark this as a temporary password
        status=data.status,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create user details
    detail = UserDetail(
        user_id=user.id,
        email=data.email,
        full_name=data.full_name
    )
    db.add(detail)
    await db.commit()

    # Return user and temporary password to send via email
    return user, temp_password



async def get_all_users(db: AsyncSession):
    result = await db.execute(
        select(UserDetail, Role.name) 
        .join(User, UserDetail.user_id == User.id) 
        .join(Role, User.role_id == Role.id)  
    )
    users = result.all()  

    return [
        {
            "full_name": detail.full_name, 
            "email": detail.email, 
            "role": role, 
            "status": detail.status
        }
        for detail, role in users
    ]

async def update_user(
    db: AsyncSession,
    user_id: int,
    data: AddUser,
    modified_by: int
) -> dict | None:
   
    res1 = await db.execute(select(User).where(User.id == user_id))
    user = res1.scalar_one_or_none()
    if not user:
        return None


    res2 = await db.execute(select(Role).where(Role.name == data.role))
    role = res2.scalar_one_or_none()
    if not role:
        raise ValueError(f"Role '{data.role}' not found")

   
    user.role_id     = role.id
    user.status      = data.status
    user.modified_by = modified_by

   
    res3 = await db.execute(select(UserDetail).where(UserDetail.user_id == user_id))
    detail = res3.scalar_one_or_none()
    if detail:
        detail.full_name = data.full_name
        detail.email     = data.email
        detail.status    = data.status


    await db.commit()


    return {
        "id":        user.id,               
        "full_name": detail.full_name,
        "email":     detail.email,
        "role":      role.name,
        "status":    detail.status,
        "is_temp_password": user.is_temp_password
    }


async def login_user(db: AsyncSession, username: str, password: str):
    q = await db.execute(
        select(User, Role.name).join(Role, User.role_id == Role.id).where(User.username == username)
    )
    result = q.first()
    if not result:
        return None

    user, role_name = result
    if verify_password(password, user.password_hash):
        return {
            "id": user.id,
            "username": user.username,
            "role": role_name,
            "is_temp_password": user.is_temp_password  # Return the temp password flag
        }

    return None


async def change_password(db: AsyncSession, username: str, new_password: str):
    q = await db.execute(select(User).where(User.username == username))
    user = q.scalar_one_or_none()
    if not user:
        return False

    # Hash the new password and update the user
    user.password_hash = hash_password(new_password)
    user.is_temp_password = False  # Reset the temp password flag

    await db.commit()

    # Send an email notifying the user about the password change
    await send_email(
        to=user.username,
        subject="Password Changed",
        body="Your password was updated."
    )
    return True


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
        sess.end_time = func.now()
        await db.commit()

async def get_current_user(
    session_uuid: str | None = Cookie(default=None, alias="session_uuid"),
    db: AsyncSession = Depends(get_db),
) -> UserListItem:
    if not session_uuid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Fetch the session
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

    # Get user details including is_temp_password
    q_user = (
        select(
            User.id.label("id"),
            UserDetail.full_name,
            UserDetail.email,
            Role.name.label("role"),
            UserDetail.status,
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


# Helper function to generate a reset token
def generate_token(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def send_reset_email(to_email, reset_token):
    sender_email = os.getenv("SMTP_USER")
    sender_password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    subject = "Password Reset Request"
    body = f"Here is your reset token: {reset_token}"

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()  # Close the connection
        print(f"Email sent to {to_email}")
    except smtplib.SMTPException as e:
        print(f"SMTP Error: {e}")
        raise Exception(f"Failed to send email: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise Exception(f"Failed to send email: {e}")