# AGENTS.md - DermaCare AI Development Guide

This file provides guidance for AI agents working in this repository.

## Project Overview

DermaCare AI is a **Dermatology Clinical Decision Support System** with:
- **Backend**: Python/FastAPI with Ollama LLM integration
- **Frontend**: Vanilla JavaScript PWA (no framework)
- **Storage**: IndexedDB for offline case storage

## Build & Run Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start development server (port 8000)
python -m uvicorn backend.app:app --reload

# Or with specific host/port
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```bash
# Serve static files (from project root)
python -m http.server 3000

# Then open http://localhost:3000 in browser
```

### Running Tests
```bash
# Run diagnosis test script
python test_diagnosis.py

# Run diagnosis test v2 (with debug logging)
python test_diagnosis_v2.py
```

## Project Structure

```
backend/
├── app.py              # FastAPI app initialization, middleware, error handling
├── routes/             # API endpoint definitions
│   ├── diagnosis_routes.py
│   ├── soap_routes.py
│   ├── drug_routes.py
│   └── case_routes.py
├── services/           # Business logic layer
│   ├── diagnosis_service.py
│   ├── soap_service.py
│   ├── drug_service.py
│   └── case_service.py
├── models/             # Pydantic request/response models
├── prompts/            # LLM prompt templates
├── ai_engine/          # Ollama client, JSON validation
└── database/           # Database utilities

frontend/
├── app.js              # Main AppController class
├── storage.js          # IndexedDB operations
├── index.html          # HTML entry point
├── styles.css          # CSS styles (CSS variables for theming)
├── manifest.json       # PWA manifest
└── service-worker.js   # Offline functionality
```

## Code Style Guidelines

### Python (Backend)

**Imports**:
- Standard library imports first, then third-party, then local
- Use absolute imports from `backend.` package
- Group by blank line between groups
```python
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.diagnosis_service import generate_diagnosis
```

**Naming Conventions**:
- Classes: `PascalCase` (e.g., `DiagnosisRequest`)
- Functions/variables: `snake_case` (e.g., `generate_diagnosis`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `DIAGNOSIS_FALLBACK`)
- Private members: `_single_underscore` prefix

**Type Annotations**:
- Use type hints for function parameters and return types
- Use `Optional[X]` over `X | None` for Python 3.9 compatibility
- Use Pydantic models for API request/response validation

**Error Handling**:
- Use FastAPI's `HTTPException` for HTTP errors
- Wrap route handlers in try/except with proper error messages
- Log errors with `logger.error()` before raising
- Return fallback responses rather than crashing on LLM failures

**Docstrings**:
- Use module-level docstrings explaining purpose
- Use docstrings for public functions/methods
- Keep lines under 88 characters

### JavaScript (Frontend)

**General Style**:
- Vanilla JS with ES6+ features (no build step required)
- Class-based architecture (`AppController`)
- Use `const`/`let` instead of `var`
- Use arrow functions for callbacks

**Naming Conventions**:
- Classes: `PascalCase` (e.g., `AppController`)
- Methods: `camelCase` (e.g., `showScreen`, `analyzeCase`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `DB_NAME`)
- DOM element IDs: `kebab-case` (e.g., `analysis-btn`)

**Async/Await**:
- Use `async/await` over raw Promises
- Always wrap in try/catch blocks
- Handle cleanup in `finally` blocks

**Security**:
- Always sanitize user input before displaying (use `sanitizeEscape()`)
- Use `textContent` over `innerHTML` when possible
- Validate all form inputs before API calls

**Performance**:
- Cache DOM element references (avoid repeated `document.getElementById`)
- Use event delegation where appropriate
- Debounce frequent operations (search, resize)

## Architecture Patterns

### Backend: Service Layer Pattern
```
Routes → Services → AI Engine/Prompts
```
- **Routes**: Handle HTTP, validate with Pydantic, return responses
- **Services**: Business logic, caching, error handling
- **AI Engine**: LLM communication, JSON validation

### Frontend: Controller Pattern
```javascript
class AppController {
  constructor() { /* init */ }
  showScreen() { /* navigation */ }
  analyzeCase() { /* API calls */ }
  // ...
}
window.app = new AppController();
```

## API Design

### Request Models (Pydantic)
```python
class DiagnosisRequest(BaseModel):
    complaint: str
    lesion: str
    symptoms: str = ""
    tests: str = ""
    geographic_region: str
    patient_age: int
```

### Response Format
All API endpoints return JSON with consistent structure:
- Success: `{"status": "ok", "data": {...}}`
- Error: Use HTTP status codes with `{"detail": "message"}`

## LLM Integration

- Uses Ollama with `phi3` model by default (configurable)
- Always validate LLM JSON output before returning to client
- Implement retry logic with fallback responses
- Cache successful LLM responses

## Environment Variables

Create `.env` from `.env.example`:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3
```

## Notes for AI Agents

1. **No npm/Node.js**: Frontend is pure vanilla JS, no build tools
2. **No TypeScript**: Plain JavaScript only
3. **No formal test framework**: Tests are manual scripts
4. **No linting configured**: Code style follows PEP 8 (Python) and ES6+ (JS)
5. **Offline-first**: Frontend works without backend for viewing history
6. **Medical context**: Be careful with medical terminology; validate against clinical accuracy
