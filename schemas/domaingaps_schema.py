from typing import Optional
from pydantic import BaseModel


class DomainGap(BaseModel):
    main_topic: Optional[str]
    count: int
