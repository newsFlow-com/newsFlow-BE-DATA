from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # IT, 금융, 정치, 사회 등
    slug = Column(String(100), nullable=False, unique=True)


class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    content = Column(Text)
    summary = Column(Text)                      # BE-AI가 생성한 요약문
    source_url = Column(Text, unique=True, nullable=False)
    publisher = Column(String(200))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    published_at = Column(DateTime(timezone=True))
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    view_count = Column(Integer, default=0)     # BE-API Redis 배치 반영 대