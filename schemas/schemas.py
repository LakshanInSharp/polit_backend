from pydantic import BaseModel, EmailStr

# Request model for adding a new user
class AddUser(BaseModel):
    full_name: str
    email: EmailStr
    role: str
    status: bool

# Request model for user login
class LoginRequest(BaseModel):
    username: str
    password: str

# Request model for changing a user's password
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

# Response model representing a user in a list
class UserListItem(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    status: bool
    is_temp_password: bool

    class Config:
        orm_mode = True

# Request model for initiating a password reset
class ForgotPasswordRequest(BaseModel):
    email: str

# Request model for resetting password with a token
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
