from typing import Optional
from pydantic import BaseModel

class QueryCount(BaseModel):
    source: str
    page_no: str
    main_topic: Optional[str]
    count: int