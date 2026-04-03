"""
Case Model - SQLAlchemy ORM model for storing clinical cases.
"""
from sqlalchemy import Column, String, Integer, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from backend.database.db_postgres import Base


class CaseRecord(Base):
    """SQLAlchemy model for clinical case records."""
    __tablename__ = "case_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(String(50), nullable=False)
    
    # Patient demographics
    patient_age = Column(Integer, nullable=True)
    geographic_region = Column(String(100), nullable=True)
    skin_phototype = Column(String(50), nullable=True)
    occupation = Column(String(200), nullable=True)
    
    # Clinical presentation
    complaint = Column(Text, nullable=True)
    lesion = Column(Text, nullable=True)
    symptoms = Column(Text, nullable=True)
    tests = Column(Text, nullable=True)
    
    # AI Analysis results (stored as JSON string)
    ai_diagnosis = Column(Text, nullable=True)
    differential_diagnosis = Column(Text, nullable=True)
    soap_note = Column(Text, nullable=True)
    treatment_plan = Column(Text, nullable=True)
    clinical_reasoning = Column(Text, nullable=True)
    
    # Metadata
    status = Column(String(50), default="pending")
    triage = Column(String(50), nullable=True)
    image_data = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<CaseRecord(case_id={self.case_id}, status={self.status})>"
