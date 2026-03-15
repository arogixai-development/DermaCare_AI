from sqlalchemy.orm import Session
from backend.models.case_model import CaseRecord

def upsert_case(db: Session, case_data: dict):
    # Check if case exists already (to handle offline resubmission)
    db_case = db.query(CaseRecord).filter(CaseRecord.case_id == case_data["case_id"]).first()
    
    if db_case:
        # Update existing record
        for key, value in case_data.items():
            setattr(db_case, key, value)
    else:
        # Create new record
        db_case = CaseRecord(**case_data)
        db.add(db_case)
    
    db.commit()
    db.refresh(db_case)
    return db_case

def get_all_cases(db: Session):
    return db.query(CaseRecord).all()

def get_case_by_id(db: Session, case_id: str):
    return db.query(CaseRecord).filter(CaseRecord.case_id == case_id).first()

def delete_case(db: Session, case_id: str):
    db_case = db.query(CaseRecord).filter(CaseRecord.case_id == case_id).first()
    if db_case:
        db.delete(db_case)
        db.commit()
        return True
    return False
