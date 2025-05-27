from datetime import datetime
from pydantic import BaseModel


class Resource(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: str  # formatted string
    uploaded_at: datetime

    class Config:
        orm_mode = True