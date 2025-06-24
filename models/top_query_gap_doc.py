from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint,JSON
from database.db import Base


class TopQueries(Base):
    __tablename__ = "top_queries"

    id = Column(Integer, primary_key=True, index=True)
    query =  Column(Text,nullable=False)
    llm_response =  Column(Text,nullable=False)
    source = Column(Text, nullable=False)
    page_no = Column(JSON, nullable=False)
    topic = Column(Text, nullable=True)
    count = Column(Integer, default=0)
    user_id      = Column(Integer, ForeignKey("user.id"), index=True)
    
    __table_args__ = (UniqueConstraint("source", "topic","query","user_id", name="uix_source_topic"),)

   


