from sqlalchemy.orm import Session
from backend.models.case_model import CaseRecord

def upsert_case(db: Session, case_data: dict, user_id: str = None):
    # Add user_id to case data
    if user_id:
        case_data["user_id"] = user_id
    
    # Check if case exists already (to handle offline resubmission)
    db_case = db.query(CaseRecord).filter(
        CaseRecord.case_id == case_data["case_id"]
    ).first()
    
    if db_case:
        # Update existing record (only if owned by this user)
        if user_id and db_case.user_id != user_id:
            raise PermissionError("Case belongs to another user")
        for key, value in case_data.items():
            setattr(db_case, key, value)
    else:
        # Create new record
        db_case = CaseRecord(**case_data)
        db.add(db_case)
    
    db.commit()
    db.refresh(db_case)
    return db_case

def get_all_cases(db: Session, user_id: str = None):
    query = db.query(CaseRecord)
    if user_id:
        query = query.filter(CaseRecord.user_id == user_id)
    return query.order_by(CaseRecord.timestamp.desc()).all()

def get_case_by_id(db: Session, case_id: str, user_id: str = None):
    query = db.query(CaseRecord).filter(CaseRecord.case_id == case_id)
    if user_id:
        query = query.filter(CaseRecord.user_id == user_id)
    return query.first()

def delete_case(db: Session, case_id: str, user_id: str = None):
    query = db.query(CaseRecord).filter(CaseRecord.case_id == case_id)
    if user_id:
        query = query.filter(CaseRecord.user_id == user_id)
    db_case = query.first()
    if db_case:
        db.delete(db_case)
        db.commit()
        return True
    return False
