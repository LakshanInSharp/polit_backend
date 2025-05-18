from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from database.db import Base, SessionLocal, sync_engine, AsyncSessionLocal
from utils.initialize_roles import initialize_roles
from routes.auth_routes import auth_router
from routes.user_routes import user_router
from service import user_service
from service.user_service import create_initial_admin_if_needed
from utils.scheduler import scheduler


# Load env
load_dotenv()

# Create tables synchronously
Base.metadata.create_all(bind=sync_engine)

# Lifespan context for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync DB session to initialize roles 
    db = SessionLocal()
    try:
        initialize_roles(db)  # <-- call your external function here
    finally:
        db.close()
    
    # Async DB session to create initial admin 
    async with AsyncSessionLocal() as async_db:
        await create_initial_admin_if_needed(async_db)

    scheduler.start()
    yield  # Application runs here
    scheduler.shutdown(wait=False)

# FastAPI instance with lifespan
app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(user_router, dependencies=[Depends(user_service.get_current_user)])
app.include_router(auth_router)

# Run app
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7000, reload=True)
