# DermaCare AI Investor Summary

## Problem

Dermatology triage and early diagnostic support can be inconsistent across settings, creating variability in care quality and referral timing. Teams need structured, reliable decision support that improves clarity without replacing clinicians.

## Solution

DermaCare AI is an AI-assisted Clinical Decision Support System that provides:

- Ranked differential diagnosis output
- Structured clinical reasoning
- SOAP-style documentation support
- Confidence/uncertainty indicators
- Escalation-aware guidance

## Technical Strengths

- Reliability pipeline with parse/validation and safe fallback behavior
- Multi-provider inference resilience architecture
- GPU-accelerated runtime operation
- Structured CDSS response format for consistent UX
- Integrated SOAP generation pathway
- Runtime observability and performance telemetry
- Repeatable benchmark validation workflow

## Final Metrics (Stable Snapshot)

Latency and reliability snapshot under stable runtime tuning:

- Quick p95: `8.11s`
- Accurate p95: `24.38s`
- timeout_spike_detected: `false`
- fallback_rate: `0.0`
- json_success_rate: `1.0`

Operational status:

- Infrastructure and runtime stack: stable
- GPU runtime: active and validated
- Benchmark process: repeatable and documented

## Safety Positioning

- DermaCare AI is **not** an autonomous diagnosis system.
- It is designed as a **clinician-assistive decision support** layer.
- Escalation-aware design prioritizes safe guidance when uncertainty is elevated.
- Final diagnosis and treatment decisions remain clinician-owned.

