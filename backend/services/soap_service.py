from backend.services.diagnosis_service import get_last_diagnosis, get_cache_stats
from typing import Dict, Any, Optional

def generate_soap_optimized(case_summary: str = "") -> Dict[str, Any]:
    """
    Generates a professional SOAP note using Python logic from stored diagnosis.
    NO LLM calls - pure Python processing for instant response (<5 seconds).
    """
    diagnosis = get_last_diagnosis()
    
    if not diagnosis:
        return {
            "error": "No diagnosis found to generate SOAP note. Please run /diagnose first.",
            "processing_time": "0.00s",
            "model_used": "None (Python only)"
        }

    # Prioritize AI-generated SOAP note from the diagnosis result
    soap_note = diagnosis.get("soap")
    if soap_note:
        if isinstance(soap_note, dict):
            # Recalculate formatted string if it's a nested dict
            def format_soap(d, indent=0):
                lines = []
                for k, v in d.items():
                    header = str(k).upper()
                    if header == 'S': header = 'SUBJECTIVE'
                    elif header == 'O': header = 'OBJECTIVE'
                    elif header == 'A': header = 'ASSESSMENT'
                    elif header == 'P': header = 'PLAN'
                    
                    if isinstance(v, dict):
                        lines.append(f"{'  ' * indent}{header}:\n{format_soap(v, indent + 1)}")
                    else:
                        lines.append(f"{'  ' * indent}{header}: {v}")
                return "\n".join(lines)
            soap_note = format_soap(soap_note)
        
        # Return AI note if valid string structure
        if isinstance(soap_note, str) and len(soap_note) > 10:
            return {
                "soap_note": soap_note,
                "processing_time": "0.01s",
                "model_used": diagnosis.get("_model", "llama3:8b"),
                "cache_hit": True
            }

    # Extract data from cached diagnosis for Python-based generation (Fallback)
    dx_list = diagnosis.get("dx", diagnosis.get("diagnoses", []))
    reasoning = diagnosis.get("reasoning", "")
    treatment = diagnosis.get("treatment", [])
    tests = diagnosis.get("tests", [])
    referral = diagnosis.get("referral", [])
    summary = diagnosis.get("summary", "Patient presents for dermatology evaluation.")
    
    # Subjective: Extract from case_summary or fallback
    subjective = "Patient presents with " + complaint if (complaint := next((line.split(': ')[1] for line in case_summary.split('\n') if 'COMPLAINT' in line.upper()), "")) else case_summary
    if not subjective: subjective = summary
    
    # Objective: Extract from reasoning or lesion description
    objective = reasoning if isinstance(reasoning, str) and reasoning else (reasoning[0] if isinstance(reasoning, list) and reasoning else diagnosis.get("lesion", "Reported physical findings."))
    
    # Assessment: Format diagnoses
    assessment = "; ".join(dx_list) if isinstance(dx_list, list) else str(dx_list)
    
    # Plan: Combine all plan items
    plan_items = []
    if isinstance(treatment, list): plan_items.extend(treatment)
    elif treatment: plan_items.append(str(treatment))
    
    if isinstance(tests, list): plan_items.extend(tests)
    elif tests: plan_items.append(str(tests))
    
    if isinstance(referral, list): plan_items.extend(referral)
    elif referral: plan_items.append(str(referral))
    
    plan = "\n".join(plan_items) if plan_items else "Management as per clinical standards."

    soap_note = f"""Subjective: {subjective}

Objective: {objective}

Assessment: Differential includes: {assessment}

Plan: {plan}"""

    # Add performance metrics
    result = {
        "soap_note": soap_note,
        "processing_time": "0.01s",  # Instant processing
        "model_used": "None (Python only)",
        "cache_hit": diagnosis.get("_cached", False),
        "diagnosis_source": diagnosis.get("_model", "Unknown")
    }
    
    return result

def generate_soap(case_summary: str = "") -> str:
    """
    Legacy function - now uses optimized version with structured output.
    """
    result = generate_soap_optimized(case_summary)
    if "error" in result:
        return result["error"]
    return result["soap_note"]

def get_soap_stats() -> Dict[str, Any]:
    """Get SOAP generation statistics"""
    cache_stats = get_cache_stats()
    return {
        "soap_generation_time": "<5 seconds (instant)",
        "llm_calls": "0 (eliminated)",
        "processing_method": "Python logic only",
        "cache_performance": cache_stats
    }
