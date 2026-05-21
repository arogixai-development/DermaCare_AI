# DermaCare AI Demo Cases

This document defines polished demo scenarios for consistent investor and product walkthroughs.

## Demo Flow Guidance

- Start with **Quick mode** for responsiveness.
- Re-run selected case in **Accurate mode** to show depth and uncertainty handling.
- Keep intake fields clean and realistic.
- Capture screenshots at consistent UI points:
  1. Intake filled
  2. Loading state
  3. Diagnosis output panel
  4. SOAP output section
  5. Confidence/uncertainty indicators

## 1) Psoriasis Case

### Intake values

- Complaint: `Chronic scaly plaques on elbows and knees`
- Lesion: `Symmetric well-demarcated erythematous plaques with silvery-white scale on extensor elbows and knees`
- Symptoms: `Itching, worse in winter`
- Age: `42`
- Region: `Urban`

### Expected behavior

- Psoriasis appears as a top differential.
- Reasoning references extensor distribution and scale characteristics.
- SOAP objective includes morphology and distribution.
- Confidence appears medium/high with explicit uncertainty framing.

### Screenshots to capture

- `screenshots/demo/01_psoriasis_intake.png`
- `screenshots/demo/01_psoriasis_output_quick.png`
- `screenshots/demo/01_psoriasis_output_accurate.png`

## 2) Fungal Infection Case

### Intake values

- Complaint: `Itchy annular rash with central clearing`
- Lesion: `Ring-shaped erythematous scaly plaque on forearm`
- Symptoms: `Itching for 2 weeks`
- Age: `28`
- Region: `Tropical`

### Expected behavior

- Fungal/tinea condition appears in top differential.
- Reasoning explicitly compares fungal morphology vs alternatives.
- SOAP plan includes confirmatory testing guidance (e.g., KOH/biopsy as applicable).

### Screenshots to capture

- `screenshots/demo/02_fungal_intake.png`
- `screenshots/demo/02_fungal_output_quick.png`
- `screenshots/demo/02_fungal_output_accurate.png`

## 3) Weak-Input Safe Fallback Case

### Intake values

- Complaint: `Rash`
- Lesion: `Red spot`
- Symptoms: `None provided`
- Age: `20`
- Region: `Urban`

### Expected behavior

- Output remains structured and safe despite minimal input richness.
- Reasoning acknowledges limited evidence and uncertainty.
- Triage and follow-up remain conservative and clinician-assistive.

### Screenshots to capture

- `screenshots/demo/03_weak_input_intake.png`
- `screenshots/demo/03_weak_input_output.png`

## 4) Low-Confidence Escalation Case

### Intake values

- Complaint: `Rapidly changing painful lesion with bleeding episodes`
- Lesion: `Irregular pigmented lesion with mixed colors and evolving borders`
- Symptoms: `Pain and intermittent bleeding`
- Age: `58`
- Region: `Urban`

### Expected behavior

- Confidence/uncertainty indicators clearly visible.
- Escalation recommendation shown when confidence is low or uncertainty high.
- Plan emphasizes urgent clinical review and confirmatory diagnostics.

### Screenshots to capture

- `screenshots/demo/04_low_confidence_intake.png`
- `screenshots/demo/04_low_confidence_output.png`

## 5) Partial Recovery Case

### Intake values

- Complaint: `Diffuse itchy plaques with inconsistent history details`
- Lesion: `Multiple poorly described lesions with variable descriptors`
- Symptoms: `Intermittent itching`
- Age: `37`
- Region: `Semi-urban`

### Expected behavior

- System returns a partial-safe but structured clinical response.
- Response indicates uncertainty and preserves CDSS fields.
- No UI crash or malformed presentation.

### Screenshots to capture

- `screenshots/demo/05_partial_recovery_intake.png`
- `screenshots/demo/05_partial_recovery_output.png`

## Demo Readiness Checklist

- Intake form validation smooth and understandable.
- Loading state is visible and non-blocking.
- Differential diagnosis, reasoning, SOAP, and confidence all render cleanly.
- Transition between Quick and Accurate modes is clear to audience.
- Screenshots are captured from the same viewport size for consistency.

