from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

users = {
    "savinya@gmail.com":{
         "id": 1,
        "username": "savinya@gmail.com",
        "password": pwd_context.hash("savinya123"),
        "full_name": "Savinya Nandakumara",
        "role_id": 2,
        "status": 1,
        "is_active": True
    },
     "thuvaraka@gmail.com":{
         "id": 2,
        "username": "thuvaraka@gmail.com",
        "password": pwd_context.hash("thuvaraka123"),
        "full_name": "Thuvaraka",
        "role_id": 3,
        "status": 1,
        "is_active": True
    }
}



def verify_password(plain_password:str, hashed_password:str) ->  bool:
    return pwd_context.verify(plain_password,hashed_password)

def get_user_by_username(username:str):
    return users.get(username)
