"""
Input Sanitization - DermaCare AI
================================
Security middleware for input validation and sanitization.
"""
import re
import html
import logging
from typing import Any, Dict, Optional, List
from fastapi import Request, HTTPException, status

logger = logging.getLogger("DermaCare_AI.sanitization")

MAX_INPUT_LENGTHS = {
    "complaint": 2000,
    "lesion": 2000,
    "symptoms": 2000,
    "patient_age": 3,
    "geographic_region": 100,
    "medical_history": 1000,
    "duration": 100,
    "drugs": 100,
    "tests": 1000,
}

MAX_TOTAL_SIZE = 10 * 1024

DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'on\w+\s*=',
    r'<iframe',
    r'<object',
    r'<embed',
    r'<link',
    r'<meta',
    r'eval\s*\(',
    r'exec\s*\(',
    r'\bunion\s+select\b',
    r'\bdrop\s+table\b',
    r'\binsert\s+into\b.*values',
]

INJECTION_PATTERNS = [
    r'[\'\";]--',
    r'\bor\s+1\s*=\s*1',
    r'\band\s+1\s*=\s*1',
    r'<[^>]*on\w+\s*=',
    r'\bexec\s*\(',
    r'\bsystem\s*\(',
]


def sanitize_string(value: str, max_length: int = 1000, strip_html: bool = True) -> str:
    """
    Sanitize a string input by removing dangerous content.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        strip_html: Whether to strip HTML tags
        
    Returns:
        Sanitized string safe for storage/processing
    """
    if not value:
        return ""
    
    if not isinstance(value, str):
        value = str(value)
    
    if len(value) > max_length:
        logger.warning(f"Input truncated from {len(value)} to {max_length} chars")
        value = value[:max_length]
    
    if strip_html:
        value = strip_html_tags(value)
    
    value = html.escape(value)
    
    value = remove_dangerous_patterns(value)
    
    value = value.strip()
    
    return value


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def remove_dangerous_patterns(value: str) -> str:
    """Remove known dangerous patterns from input."""
    for pattern in DANGEROUS_PATTERNS:
        value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)
    return value


def validate_input_size(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate total input size doesn't exceed limits.
    
    Returns:
        (is_valid, error_message)
    """
    total_size = 0
    
    for key, value in data.items():
        if isinstance(value, str):
            total_size += len(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    total_size += len(item)
    
    if total_size > MAX_TOTAL_SIZE:
        return False, f"Total input size ({total_size} bytes) exceeds limit ({MAX_TOTAL_SIZE} bytes)"
    
    return True, None


def sanitize_diagnosis_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize diagnosis API input.
    
    Args:
        data: Raw diagnosis request data
        
    Returns:
        Sanitized diagnosis data
        
    Raises:
        HTTPException: If input validation fails
    """
    if not validate_input_size(data)[0]:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request payload too large"
        )
    
    sanitized = {}
    
    if "complaint" in data:
        sanitized["complaint"] = sanitize_string(
            data["complaint"], 
            MAX_INPUT_LENGTHS["complaint"]
        )
    
    if "lesion" in data:
        sanitized["lesion"] = sanitize_string(
            data["lesion"],
            MAX_INPUT_LENGTHS["lesion"]
        )
    
    if "symptoms" in data:
        sanitized["symptoms"] = sanitize_string(
            data["symptoms"],
            MAX_INPUT_LENGTHS["symptoms"]
        )
    
    if "patient_age" in data:
        try:
            age = int(data["patient_age"])
            if age < 0 or age > 150:
                raise ValueError("Age out of range")
            sanitized["patient_age"] = age
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid patient_age: must be integer 0-150"
            )
    
    if "geographic_region" in data:
        sanitized["geographic_region"] = sanitize_string(
            data["geographic_region"],
            MAX_INPUT_LENGTHS["geographic_region"]
        )
    
    if "history_duration" in data:
        sanitized["history_duration"] = sanitize_string(
            data["history_duration"],
            MAX_INPUT_LENGTHS["duration"]
        )
    
    if "skin_phototype" in data:
        sanitized["skin_phototype"] = sanitize_string(
            data["skin_phototype"],
            20
        )
    
    if "medical_history" in data:
        sanitized["medical_history"] = sanitize_string(
            data["medical_history"],
            MAX_INPUT_LENGTHS["medical_history"]
        )
    
    if "tests" in data:
        sanitized["tests"] = sanitize_string(
            data["tests"],
            MAX_INPUT_LENGTHS["tests"]
        )
    
    if "image_data" in data:
        sanitized["image_data"] = data["image_data"][:2 * 1024 * 1024]
    
    return sanitized


def sanitize_soap_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize SOAP API input."""
    sanitized = {}
    
    for field in ["case_id", "complaint", "lesion", "symptoms", "region"]:
        if field in data and data[field]:
            max_len = MAX_INPUT_LENGTHS.get(field, 2000)
            sanitized[field] = sanitize_string(data[field], max_len)
    
    if "patient_age" in data:
        try:
            sanitized["patient_age"] = max(0, min(150, int(data["patient_age"])))
        except (ValueError, TypeError):
            pass
    
    if "diagnoses" in data and isinstance(data["diagnoses"], list):
        sanitized["diagnoses"] = [
            sanitize_string(d, 200) if isinstance(d, str) else d
            for d in data["diagnoses"][:20]
        ]
    
    if "treatment" in data and isinstance(data["treatment"], list):
        sanitized["treatment"] = [
            sanitize_string(t, 500) if isinstance(t, str) else t
            for t in data["treatment"][:50]
        ]
    
    return sanitized


def sanitize_drug_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize drug interaction API input."""
    sanitized = {}
    
    if "drugs" in data and isinstance(data["drugs"], list):
        sanitized["drugs"] = [
            sanitize_string(drug, MAX_INPUT_LENGTHS["drugs"])
            for drug in data["drugs"][:50]
        ]
    
    return sanitized


def check_for_injection(value: str) -> bool:
    """Check if a value contains injection patterns."""
    value_lower = value.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, value_lower, re.IGNORECASE):
            logger.warning(f"Potential injection detected: {pattern}")
            return True
    return False


def validate_diagnosis_data(data: Dict[str, Any]) -> List[str]:
    """
    Validate diagnosis data and return list of issues.
    Empty list means valid.
    """
    issues = []
    
    if not data.get("complaint") and not data.get("lesion"):
        issues.append("At least one of 'complaint' or 'lesion' is required")
    
    if data.get("patient_age"):
        age = data.get("patient_age")
        if not isinstance(age, int) or age < 0 or age > 150:
            issues.append("patient_age must be integer 0-150")
    
    return issues
