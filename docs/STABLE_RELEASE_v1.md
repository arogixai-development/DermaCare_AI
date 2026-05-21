# DermaCare AI Stable Release v1

## System Overview

DermaCare AI is a clinician-assistive dermatology Clinical Decision Support System (CDSS) designed to provide structured diagnostic support, SOAP output, treatment guidance, and safety escalation hints.

- **Architecture positioning:** FastAPI backend + Ollama inference + reliability/fallback orchestration + structured JSON/CDSS response shaping + vanilla JS frontend.
- **CDSS scope:** Decision support for triage and differential reasoning, not autonomous diagnosis.
- **Modes:**
  - **Quick mode:** Lower latency, partial-safe behavior when needed.
  - **Accurate mode:** Higher depth and uncertainty handling with longer latency budget.
- **Reliability pipeline (stable):**
  - Parse-and-validate gate
  - Partial salvage path for usable outputs
  - Fallback path when upstream generation fails
  - Runtime observability and benchmarked latency/reliability metrics

## Runtime Configuration (Final Working)

Use the following runtime settings for stable GPU-backed operation:

- `OLLAMA_GPU_LAYERS=999`
- `CUDA_VISIBLE_DEVICES=0`
- `OLLAMA_CONTEXT_LENGTH=2048`
- `OLLAMA_NUM_PARALLEL=1`
- `OLLAMA_MAX_LOADED_MODELS=1`

Recommended model for this stable snapshot:

- `OLLAMA_MODEL=phi3:latest`

## Final Benchmark Results

Final tuned benchmark snapshot:

- **Quick p95:** `8.11s`
- **Accurate p95:** `24.38s`
- **timeout_spike_detected:** `false`
- **fallback_rate:** `0.0`
- **json_success_rate:** `1.0`

Additional stability notes:

- GPU active with Ollama processor offload verified in runtime.
- Latest `/metrics` snapshot remained within target latency envelope (`timeout_spike_detected=false`).

## Known Limitations

- **Phi3 reasoning variability:** Narrative style and clinical phrasing may vary between runs.
- **Partial outputs still possible:** Partial-safe responses can still occur by design under uncertain parse conditions.
- **Confidence limitations:** Confidence can be interpreted inconsistently by non-clinical users if not accompanied by explanatory context.
- **Reasoning richness evolving:** Compare/contrast depth across top differential diagnoses is improved but still not equivalent to specialist-authored notes in all cases.

## Final Status

- **Infrastructure:** Stable
- **Runtime/latency system:** Stable with GPU-tuned configuration
- **Investor performance gate (latency objective):** Passed
- **Clinical UX refinement:** Ongoing and prioritized for polish iterations

