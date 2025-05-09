import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()


DATABASE_URL_ASYNC = os.getenv("DATABASE_URL_ASYNC")
DATABASE_URL_SYNC  = os.getenv("DATABASE_URL_SYNC")

engine = create_async_engine(DATABASE_URL_ASYNC, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(DATABASE_URL_SYNC, echo=True)
SessionLocal = sessionmaker(bind=sync_engine, class_=Session, expire_on_commit=False)

Base = declarative_base()
