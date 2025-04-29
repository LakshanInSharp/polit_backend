from fastapi import  FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from routes.user_routes import router as user_router
import uvicorn

app = FastAPI()


# allow frontend to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 


)

app.add_middleware(SessionMiddleware, secret_key="my_dev_secret_123",same_site="Lax",max_age=60*60 )

app.include_router(user_router, prefix="/api/users")

if __name__ == "__main__":
   
    uvicorn.run(app, host="0.0.0.0", port=7000)