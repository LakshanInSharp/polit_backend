from datetime import date
from pydantic import BaseModel


class Resource(BaseModel):
    id: int
    name: str
    type: str
    size: str
    date_uploaded: date