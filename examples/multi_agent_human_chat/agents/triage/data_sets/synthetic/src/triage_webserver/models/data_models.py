import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from triage_webserver.database.base import Base


class Dataset(Base):
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    total_examples = Column(Integer, default=0)
    model = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship with Examples
    examples = relationship("Example", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dataset(id={self.id}, name='{self.name}', total_examples={self.total_examples})>"


class Example(Base):
    __tablename__ = "examples"
    
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    conversation = Column(Text, nullable=False)
    target_agent = Column(String(100), nullable=False)
    turns = Column(Integer, nullable=False)
    temperature = Column(Float, nullable=False)
    index_batch = Column(Integer, nullable=True)
    total_batch = Column(Integer, nullable=True)
    special_case = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship with Dataset
    dataset = relationship("Dataset", back_populates="examples")

    def __repr__(self):
        return f"<Example(id={self.id}, target_agent='{self.target_agent}', turns={self.turns})>"