from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import Base, SessionLocal, sync_engine, AsyncSessionLocal  # Corrected async session import
from models.user_model import Role
from routes.user_routes import router as user_router
from service.user_service import create_initial_admin_if_needed  # Import from user_service

# Create all tables (synchronously)
Base.metadata.create_all(bind=sync_engine)

# Insert default roles if not exist
def initialize_roles():
    db = SessionLocal()
    try:
        default_roles = ["admin", "system_admin", "user"]
        for role_name in default_roles:
            if not db.query(Role).filter_by(name=role_name).first():
                db.add(Role(name=role_name))
        db.commit()
    finally:
        db.close()

initialize_roles()

# Instantiate FastAPI app
app = FastAPI()
load_dotenv()

# Enable CORS for your frontend (React, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your application routes
app.include_router(user_router)

# Run async startup logic
@app.on_event("startup")
async def startup_event():
    # Get a database session using the async session factory
    async with AsyncSessionLocal() as db:
        await create_initial_admin_if_needed(db)  # Pass db to the function

# Run with Uvicorn if executed directly
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7000, reload=True)
