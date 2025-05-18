import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Load environment variables from .env file
load_dotenv()

# Get the asynchronous and synchronous database URLs from environment variables
DATABASE_URL_ASYNC = os.getenv("DATABASE_URL_ASYNC")
DATABASE_URL_SYNC  = os.getenv("DATABASE_URL_SYNC")

# Create an asynchronous engine and session factory for async database operations
engine = create_async_engine(DATABASE_URL_ASYNC, echo=True, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Create a synchronous engine and session factory for sync database operations
sync_engine = create_engine(DATABASE_URL_SYNC, echo=True)
SessionLocal = sessionmaker(bind=sync_engine, class_=Session, expire_on_commit=False)

# Declare the base class for ORM models
Base = declarative_base()
