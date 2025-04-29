from fastapi import APIRouter, Request, HTTPException

from models.login import UserLogin
from service.user_service import get_user_by_username, verify_password, users
from uuid import uuid4
router = APIRouter()
#Dummy sessions list
sessions = []
@router.post("/login")
async def login_user(request: Request, credentials: UserLogin):
    try:
        user = get_user_by_username(credentials.username)
        if user and verify_password(credentials.password, user["password"]):
            request.session.clear()
            request.session["user_id"] = user["id"]
            # Create a dummy session
            session = {
                "SessionID": len(sessions) + 1,
                "UserID": user["id"],
                "SessionUUID": str(uuid4()),
                "Start": None,
                "End": None,
                "Status": None
            }
            sessions.append(session)  # Add to dummy list
            return {
                "message": "Logged in successfully!",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role_id": user["role_id"],
                    "status": user["status"],
                    "is_active": user["is_active"]
                }
            }
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/me")
async def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        user = next((u for u in users.values() if u["id"] == user_id), None)
        if user:
            return {"message": "Session active", "user": user}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        raise HTTPException(status_code=401, detail="Not logged in")
    

@router.post("/logout")
async def logout_user(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}
@router.get("/sessions")
async def get_sessions():
    return {"sessions": sessions}