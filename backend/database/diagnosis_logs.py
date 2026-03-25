"""
Diagnosis Logs Database - DermaCare AI
====================================
Stores all diagnosis requests and AI reasoning chains for transparency.
"""
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger("DermaCare_AI.diagnosis_logs")

BASE_DIR = Path(__file__).parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

DIAGNOSIS_DB = LOGS_DIR / "diagnosis_logs.db"


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(str(DIAGNOSIS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_diagnosis_db():
    """Initialize diagnosis logs database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            patient_age INTEGER,
            geographic_region TEXT,
            complaint TEXT,
            lesion TEXT,
            symptoms TEXT,
            llm_prompt TEXT,
            llm_response TEXT,
            diagnoses TEXT,
            clinical_reasoning TEXT,
            confidence_score REAL,
            monte_carlo_enabled INTEGER,
            uncertainty_interval TEXT,
            gmu_analysis TEXT,
            user_feedback TEXT,
            feedback_timestamp TEXT,
            processing_time_ms REAL
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON diagnosis_logs(timestamp)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_case_id ON diagnosis_logs(case_id)
    """)
    
    conn.commit()
    conn.close()
    logger.info("Diagnosis logs database initialized")


def log_diagnosis(
    case_id: str,
    patient_data: Dict[str, Any],
    llm_prompt: str,
    llm_response: str,
    diagnoses: List[Dict],
    clinical_reasoning: str,
    confidence_score: Optional[float] = None,
    monte_carlo_enabled: bool = False,
    uncertainty_interval: Optional[List[float]] = None,
    gmu_analysis: Optional[Dict] = None,
    processing_time_ms: Optional[float] = None
) -> int:
    """
    Log a diagnosis request and response.
    
    Returns the log entry ID.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO diagnosis_logs (
            case_id, timestamp, patient_age, geographic_region,
            complaint, lesion, symptoms, llm_prompt, llm_response,
            diagnoses, clinical_reasoning, confidence_score,
            monte_carlo_enabled, uncertainty_interval, gmu_analysis,
            processing_time_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id,
        datetime.now(timezone.utc).isoformat(),
        patient_data.get("patient_age"),
        patient_data.get("geographic_region"),
        patient_data.get("complaint"),
        patient_data.get("lesion"),
        patient_data.get("symptoms"),
        llm_prompt,
        llm_response,
        json.dumps(diagnoses),
        clinical_reasoning,
        confidence_score,
        1 if monte_carlo_enabled else 0,
        json.dumps(uncertainty_interval) if uncertainty_interval else None,
        json.dumps(gmu_analysis) if gmu_analysis else None,
        processing_time_ms
    ))
    
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Logged diagnosis: case_id={case_id}, log_id={log_id}")
    return log_id


def add_user_feedback(log_id: int, feedback: str) -> bool:
    """
    Add user feedback to a diagnosis log.
    
    feedback: 'positive' or 'negative'
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE diagnosis_logs
        SET user_feedback = ?, feedback_timestamp = ?
        WHERE id = ?
    """, (feedback, datetime.now(timezone.utc).isoformat(), log_id))
    
    rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows > 0


def get_diagnosis_log(log_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific diagnosis log entry."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM diagnosis_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_recent_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent diagnosis logs."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, case_id, timestamp, patient_age, geographic_region,
               confidence_score, monte_carlo_enabled, user_feedback
        FROM diagnosis_logs
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_logs_by_case(case_id: str) -> List[Dict[str, Any]]:
    """Get all logs for a specific case."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM diagnosis_logs
        WHERE case_id = ?
        ORDER BY timestamp DESC
    """, (case_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN user_feedback = 'positive' THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN user_feedback = 'negative' THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN user_feedback IS NULL THEN 1 ELSE 0 END) as pending
        FROM diagnosis_logs
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    total = row[0] or 0
    positive = row[1] or 0
    negative = row[2] or 0
    pending = row[3] or 0
    
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "pending": pending,
        "positive_rate": round(positive / total * 100, 1) if total > 0 else 0
    }


def get_decision_log(log_id: int) -> Dict[str, Any]:
    """
    Get complete decision log for explainability.
    
    Returns structured data for frontend "Why this diagnosis?" feature.
    """
    log = get_diagnosis_log(log_id)
    
    if not log:
        return {"error": "Log not found"}
    
    return {
        "case_id": log["case_id"],
        "timestamp": log["timestamp"],
        "patient": {
            "age": log["patient_age"],
            "region": log["geographic_region"]
        },
        "input": {
            "complaint": log["complaint"],
            "lesion": log["lesion"],
            "symptoms": log["symptoms"]
        },
        "diagnoses": json.loads(log["diagnoses"]) if log["diagnoses"] else [],
        "clinical_reasoning": log["clinical_reasoning"],
        "confidence": {
            "score": log["confidence_score"],
            "monte_carlo_enabled": bool(log["monte_carlo_enabled"]),
            "uncertainty_interval": json.loads(log["uncertainty_interval"]) if log["uncertainty_interval"] else None
        },
        "gmu_analysis": json.loads(log["gmu_analysis"]) if log["gmu_analysis"] else None,
        "llm_prompt": log["llm_prompt"],
        "processing_time_ms": log["processing_time_ms"],
        "feedback": {
            "user_feedback": log["user_feedback"],
            "timestamp": log["feedback_timestamp"]
        }
    }


init_diagnosis_db()
