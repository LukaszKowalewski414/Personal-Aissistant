from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Table, ForeignKey, desc
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

DB_PATH = os.getenv("DB_PATH", "meetings.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

item_tag = Table(
    "item_tag", Base.metadata,
    Column("item_id", ForeignKey("items.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    kind = Column(String(16), index=True)            # 'meeting' | 'email'
    title = Column(String(200), default="")
    happened_at = Column(DateTime, index=True, default=datetime.utcnow)

    # --- Twoje nowe pola (TU, wewnątrz klasy!) ---
    participants = Column(String(200), default="")
    client = Column(String(200), default="")
    topic = Column(String(200), default="")
    sales_score = Column(Integer, default=None)
    sales_comment = Column(Text, default="")
    next_steps = Column(Text, default="")            # JSON (lista kroków)
    duration_sec = Column(Integer, default=None)
    audio_quality = Column(String(16), default="")   # low/med/high
    file_hash = Column(String(64), index=True, unique=True)

    language = Column(String(10), default="")
    transcript = Column(Text, default="")
    summary = Column(Text, default="")
    tasks = Column(Text, default="")
    ideas = Column(Text, default="")
    source_path = Column(String(500), default="")

    tags = relationship("Tag", secondary=item_tag, back_populates="items")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, index=True)
    items = relationship("Item", secondary=item_tag, back_populates="tags")

def init_db():
    Base.metadata.create_all(engine)
