"""
HL7 FHIR-Inspired SOAP Templates - DermaCare AI
==============================================
Structured clinical note templates following HL7 FHIR principles.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

FHIR_SOAP_TEMPLATE = """**CLINICAL ENCOUNTER NOTE**
Generated: {timestamp}
Practitioner: DermaCare AI Clinical Decision Support

═══════════════════════════════════════════════════════════════

**SUBJECTIVE (S)**
───────────────────────────────────────────────────────────────
Chief Complaint: {complaint}

History of Present Illness:
{lesion}

Symptoms:
{symptoms}

Patient Demographics:
- Age: {patient_age} years
- Region: {geographic_region}

═══════════════════════════════════════════════════════════════

**OBJECTIVE (O)**
───────────────────────────────────────────────────────────────
Physical Examination:
{lesion_description}

Vital Signs: Not recorded (field conditions)

Diagnostic Findings:
{test_results}

═══════════════════════════════════════════════════════════════

**ASSESSMENT (A)**
───────────────────────────────────────────────────────────────
Primary Diagnosis: {primary_diagnosis}

Differential Diagnoses:
{differential_diagnoses}

Clinical Reasoning:
{clinical_reasoning}

═══════════════════════════════════════════════════════════════

**PLAN (P)**
───────────────────────────────────────────────────────────────
Treatment:
{treatment}

Investigations:
{investigations}

Patient Education:
{patient_education}

Follow-up:
{followup}

═══════════════════════════════════════════════════════════════

**FHIR-RESOURCES**
───────────────────────────────────────────────────────────────
Condition:
- code: {diagnosis_code}
- severity: {severity}
- encounter: {encounter_id}

MedicationRequest:
{medications}

═══════════════════════════════════════════════════════════════
"""


COMPACT_SOAP_TEMPLATE = """**SOAP NOTE - {timestamp}**

S: {complaint} | {symptoms}
O: {lesion}
A: {diagnoses}
P: {treatment}

Patient: {patient_age}yo | {geographic_region}
"""


DETAILED_SOAP_TEMPLATE = """**DETAILED CLINICAL DOCUMENTATION**
============================================================

PATIENT INFORMATION
------------------
Age: {patient_age}
Geographic Region: {geographic_region}
Date: {timestamp}

CLINICAL HISTORY
---------------
Chief Complaint: {complaint}
Lesion Description: {lesion}
Reported Symptoms: {symptoms}

DIAGNOSTIC ASSESSMENT
--------------------
Primary: {primary_diagnosis}
Differentials: {differential_diagnoses}

Reasoning: {clinical_reasoning}

TREATMENT PLAN
--------------
Medications: {treatment}
Tests: {investigations}
Follow-up: {followup}

============================================================
DermaCare AI | FHIR-Inspired Clinical Documentation
"""


def format_fhir_soap(
    case_data: Dict[str, Any],
    diagnoses: List[str] = None,
    treatment: List[str] = None,
    template: str = "detailed"
) -> str:
    """
    Format SOAP note using HL7 FHIR-inspired template.
    
    Args:
        case_data: Patient case information
        diagnoses: List of diagnoses
        treatment: List of treatments
        template: Template type ('fhir', 'compact', 'detailed')
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    complaint = case_data.get("complaint", "Dermatological examination")
    lesion = case_data.get("lesion", "Not specified")
    symptoms = case_data.get("symptoms", "None reported")
    age = case_data.get("patient_age", "Unknown")
    region = case_data.get("geographic_region", "Unknown")
    
    diagnoses_list = diagnoses or case_data.get("diagnoses_list", [])
    if isinstance(diagnoses_list, list):
        diagnoses_str = "\n".join([f"  - {d}" for d in diagnoses_list[:5]])
    else:
        diagnoses_str = str(diagnoses_list)
    
    treatment_list = treatment or case_data.get("treatment_list", [])
    if isinstance(treatment_list, list):
        treatment_str = "\n".join([f"  - {t}" for t in treatment_list[:5]])
    else:
        treatment_str = str(treatment_list)
    
    primary = diagnoses_list[0] if diagnoses_list else "Pending clinical correlation"
    differentials = diagnoses_str
    
    if template == "fhir":
        return FHIR_SOAP_TEMPLATE.format(
            timestamp=timestamp,
            complaint=complaint,
            lesion=lesion,
            symptoms=symptoms,
            patient_age=age,
            geographic_region=region,
            lesion_description=f"Visual inspection: {lesion}",
            test_results="Pending laboratory correlation",
            primary_diagnosis=primary,
            differential_diagnoses=differentials,
            clinical_reasoning="Based on clinical presentation and AI-assisted analysis",
            treatment=treatment_str or "- Standard dermatological care",
            investigations="- Skin biopsy if indicated\n- Follow-up as needed",
            patient_education="- Monitor for changes\n- Report worsening symptoms",
            followup="1-2 weeks or as clinically indicated",
            diagnosis_code="DX001 (dermatological condition)",
            severity="Moderate",
            encounter_id=f"ENC-{datetime.now().strftime('%Y%m%d%H%M')}",
            medications=treatment_str or "None prescribed"
        )
    
    elif template == "compact":
        return COMPACT_SOAP_TEMPLATE.format(
            timestamp=timestamp,
            complaint=complaint,
            symptoms=symptoms,
            lesion=lesion,
            diagnoses=differentials or "Pending",
            treatment=treatment_str or "TBD",
            patient_age=age,
            geographic_region=region
        )
    
    else:
        return DETAILED_SOAP_TEMPLATE.format(
            timestamp=timestamp,
            complaint=complaint,
            lesion=lesion,
            symptoms=symptoms,
            patient_age=age,
            geographic_region=region,
            primary_diagnosis=primary,
            differential_diagnoses=differentials,
            clinical_reasoning="Comprehensive clinical assessment based on presented symptoms and AI analysis",
            treatment=treatment_str or "Standard dermatological management",
            investigations="As clinically indicated",
            followup="1-2 weeks or as needed"
        )


def get_available_templates() -> List[Dict[str, str]]:
    """Get list of available SOAP templates."""
    return [
        {
            "id": "detailed",
            "name": "Detailed Clinical Documentation",
            "description": "Comprehensive format with all sections",
            "fields": ["complaint", "lesion", "symptoms", "diagnoses", "treatment"]
        },
        {
            "id": "fhir",
            "name": "FHIR-Inspired Format",
            "description": "HL7 FHIR-structured clinical note",
            "fields": ["complaint", "lesion", "symptoms", "diagnoses", "treatment", "plan"]
        },
        {
            "id": "compact",
            "name": "Compact Summary",
            "description": "Quick one-page summary format",
            "fields": ["complaint", "symptoms", "diagnosis", "treatment"]
        }
    ]


def validate_template_data(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate SOAP template data.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    if not data.get("complaint") and not data.get("lesion"):
        errors.append("Either 'complaint' or 'lesion' is required")
    
    if data.get("patient_age"):
        try:
            age = int(data["patient_age"])
            if age < 0 or age > 150:
                errors.append("Patient age must be 0-150")
        except (ValueError, TypeError):
            errors.append("Patient age must be a number")
    
    return len(errors) == 0, errors
