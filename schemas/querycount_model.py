from typing import Optional
from pydantic import BaseModel

class FileCount(BaseModel):
    source: str
    # page_no: str
    count: int

class QueryCount(BaseModel):
    source: str
    page_no: str
    count: int
    main_topic:Optional[str]