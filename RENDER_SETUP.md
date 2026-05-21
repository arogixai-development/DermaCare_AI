# Deployment Guide (Paused)

Deployment process is intentionally on hold for now.

## Current focus

- Stabilize local functionality
- Improve `phi3` output parsing and fallback behavior
- Validate authentication/session edge cases
- Enable investor-grade reliability pipeline with feature flags

## Local runtime

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

## Local environment notes

- Use `OLLAMA_BASE_URL=http://localhost:11434`
- Keep `OLLAMA_MODEL=phi3`
- Keep frontend pointed to local backend during validation
- For contingency fallback tests set `GROQ_API_KEY` and keep `QUICK_ALLOW_GROQ_FALLBACK=false`

Deployment instructions (Render/tunnel/cloud setup) will be reintroduced after local validation is complete.
