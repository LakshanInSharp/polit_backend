import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Load environment variables from .env file
load_dotenv()

# Get individual components from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")  # Default to 5432 if not provided
DB_NAME = os.getenv("DB_NAME")

# Construct database URLs
DATABASE_URL_ASYNC = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL_SYNC = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create an asynchronous engine and session factory
engine = create_async_engine(
    DATABASE_URL_ASYNC,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Create a synchronous engine and session factory
sync_engine = create_engine(
    DATABASE_URL_SYNC,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False
)



# Declare the base class for ORM models
Base = declarative_base()
