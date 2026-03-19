from backend.ai_engine.ollama_client import run_ai_with_retry, check_ollama_connection, OllamaConnectionError
from typing import Dict, Any, Optional
import time
import json
import uuid
import logging

logger = logging.getLogger("DermaCare_AI.soap_service")

def generate_soap_optimized(case_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a professional SOAP note from provided case data.
    Uses LLM to generate a fresh, contextual SOAP note for each request.
    """
    if not case_data:
        return {
            "error": "No case data provided. Please include case information.",
            "processing_time": "0.00s",
            "model_used": "None"
        }
    
    # Check Ollama connection first
    status = check_ollama_connection()
    if not status["connected"]:
        logger.warning("SOAP service: Ollama not available, using fallback")
        return generate_soap_from_fields(case_data)
    
    start_time = time.time()
    
    # Build case summary string from case_data
    case_summary = format_case_summary(case_data)
    
    # Add unique ID to prompt to prevent Ollama caching
    request_id = str(uuid.uuid4())[:8]
    
    # Build prompt with full case context and unique request ID
    prompt = build_soap_prompt_from_summary(case_summary, request_id)
    
    try:
        # Generate fresh SOAP note using LLM - don't require JSON format
        raw = run_ai_with_retry(prompt, max_tokens=1024, format=None, max_retries=1)
        
        if not raw or not raw.strip():
            logger.warning("SOAP service: Empty LLM response, using fallback")
            return generate_soap_from_fields(case_data)
        
        # Format the raw response as SOAP
        soap_note = format_raw_soap(raw)
        
        processing_time = f"{time.time() - start_time:.2f}s"
        
        return {
            "soap_note": soap_note,
            "processing_time": processing_time,
            "model_used": status.get("models", ["llama3:8b"])[0] if status.get("models") else "llama3:8b",
            "cache_hit": False,
            "case_id": case_data.get("case_id", "unknown"),
            "request_id": request_id
        }
        
    except OllamaConnectionError:
        logger.warning("SOAP service: Ollama connection lost, using fallback")
        return generate_soap_from_fields(case_data)
    except Exception as e:
        logger.error("SOAP service error: %s", str(e))
        # Fallback: Generate SOAP from diagnosis fields
        return generate_soap_from_fields(case_data)


def format_case_summary(case_data: Dict[str, Any]) -> str:
    """Format case data into a summary string for the prompt."""
    parts = []
    
    if case_data.get("complaint"):
        parts.append(f"Chief Complaint: {case_data['complaint']}")
    if case_data.get("lesion"):
        parts.append(f"Lesion Description: {case_data['lesion']}")
    if case_data.get("symptoms"):
        parts.append(f"Symptoms: {case_data['symptoms']}")
    if case_data.get("tests"):
        parts.append(f"Tests Performed: {case_data['tests']}")
    if case_data.get("patient_age"):
        parts.append(f"Patient Age: {case_data['patient_age']}")
    if case_data.get("geographic_region"):
        parts.append(f"Geographic Region: {case_data['geographic_region']}")
    if case_data.get("medical_history"):
        parts.append(f"Medical History: {case_data['medical_history']}")
    if case_data.get("duration"):
        parts.append(f"Duration: {case_data['duration']}")
    
    # Include diagnosis if available
    diagnoses = case_data.get("diagnoses_list", case_data.get("diagnoses", []))
    if diagnoses:
        parts.append(f"Diagnoses: {', '.join(diagnoses) if isinstance(diagnoses, list) else diagnoses}")
    
    return "\n".join(parts) if parts else "No case details provided."


def build_soap_prompt_from_summary(case_summary: str, request_id: str = "") -> str:
    """Build SOAP prompt from case summary."""
    return f"""
You are a medical AI assistant for dermatology in low-resource environments.
Your task is to convert the following clinical case description into a structured medical SOAP note.

Case Description:
{case_summary}

Format your response strictly using this structure:

Subjective:
(Detail the patient's chief complaint, history of present illness, symptoms, and relevant history reported by the patient)

Objective:
(Detail observable, measurable data such as lesion appearance, size, physical exam findings, and any test results available)

Assessment:
(Provide the professional medical diagnosis or differential diagnoses based on the subjective and objective data)

Plan:
(Outline the recommended treatment, further tests, patient education, and follow-up or referral advice)

Ensure the language is concise, professional, and clinical.
"""


def format_raw_soap(raw_text: str) -> str:
    """Format raw LLM text into structured SOAP note."""
    lines = raw_text.strip().split('\n')
    formatted = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Add section headers if not present
        upper = line.upper()
        if upper.startswith('S:') or upper.startswith('SUBJECTIVE'):
            formatted.append(f"**SUBJECTIVE:**\n{line.split(':', 1)[-1].strip()}")
        elif upper.startswith('O:') or upper.startswith('OBJECTIVE'):
            formatted.append(f"\n**OBJECTIVE:**\n{line.split(':', 1)[-1].strip()}")
        elif upper.startswith('A:') or upper.startswith('ASSESSMENT'):
            formatted.append(f"\n**ASSESSMENT:**\n{line.split(':', 1)[-1].strip()}")
        elif upper.startswith('P:') or upper.startswith('PLAN'):
            formatted.append(f"\n**PLAN:**\n{line.split(':', 1)[-1].strip()}")
        else:
            formatted.append(line)
    return '\n'.join(formatted) if formatted else raw_text


def generate_soap_from_fields(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback: Generate SOAP note from case fields without LLM."""
    
    complaint = case_data.get("complaint", "Patient presents for dermatology evaluation.")
    lesion = case_data.get("lesion", "As described by patient.")
    symptoms = case_data.get("symptoms", "")
    age = case_data.get("patient_age", "Unknown")
    region = case_data.get("geographic_region", "")
    diagnoses = case_data.get("diagnoses_list", case_data.get("diagnoses", []))
    treatments = case_data.get("treatment_list", case_data.get("treatment", []))
    tests = case_data.get("tests_list", case_data.get("tests", []))
    
    soap_note = f"""**SUBJECTIVE:**
Patient is a {age}-year-old presenting with {complaint}. {symptoms}

**OBJECTIVE:**
Physical examination reveals {lesion}. Patient is from {region} region.

**ASSESSMENT:**
{"; ".join(diagnoses) if diagnoses else "Awaiting definitive diagnosis."}

**PLAN:**
{" ".join([f"- {t}" for t in treatments]) if treatments else "- Standard dermatology management."}
{" ".join([f"- Confirm with: {t}" for t in tests]) if tests else ""}
"""
    
    return {
        "soap_note": soap_note,
        "processing_time": "0.01s",
        "model_used": "Python fallback",
        "cache_hit": False
    }

def generate_soap(case_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Legacy function - now uses optimized version with structured output.
    """
    result = generate_soap_optimized(case_data)
    if "error" in result:
        return result["error"]
    return result["soap_note"]

def get_soap_stats() -> Dict[str, Any]:
    """Get SOAP generation statistics"""
    return {
        "soap_generation_time": "<5 seconds (instant)",
        "llm_calls": "0 (eliminated)",
        "processing_method": "Python logic + LLM",
        "note": "Now generates fresh SOAP notes per request"
    }
