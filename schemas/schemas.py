from pydantic import BaseModel, EmailStr

class AddUser(BaseModel):
    full_name: str
    email: EmailStr
    role: str
    status: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
     old_password: str
     new_password: str
     confirm_password: str

class UserListItem(BaseModel):
    id:        int
    full_name: str
    email:     EmailStr
    role:      str
    status:    bool
    is_temp_password: bool
    

    class Config:
        orm_mode = True



# Create a model for the request
class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str