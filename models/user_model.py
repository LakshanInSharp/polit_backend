from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from database.db import Base

class Role(Base):
    __tablename__ = "role"
    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class User(Base):
    __tablename__ = "user"
    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id       = Column(Integer, ForeignKey("role.id"), nullable=False)
    status        = Column(Boolean, default=True)
    created_by    = Column(Integer, nullable=True)
    created_date  = Column(DateTime, server_default=func.now())
    modified_by   = Column(Integer, nullable=True)
    modified_date = Column(DateTime, onupdate=func.now())
    is_temp_password = Column(Boolean, default=True)


    role     = relationship("Role")
    sessions = relationship("Session", back_populates="user")
    user_detail = relationship("UserDetail", backref="user", uselist=False)
    reset_tokens = relationship("PasswordResetToken", back_populates="user")


class UserDetail(Base):
    __tablename__ = "user_detail"
    user_detail_id        = Column(Integer, primary_key=True)
    user_id   = Column(Integer, ForeignKey("user.id"))
    email     = Column(String, nullable=False, unique=True)  # Ensure email is unique
    full_name = Column(String, nullable=False)
    status    = Column(Boolean, default=True)

class Session(Base):
    __tablename__ = "session"
    session_id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("user.id"), index=True)
    session_uuid = Column(String, nullable=False)
    start_time   = Column(DateTime, server_default=func.now())
    end_time     = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    token = Column(String, nullable=False, unique=True)
    expiration = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="reset_tokens")
