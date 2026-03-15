from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.diagnosis_routes import router as diagnosis_router
from backend.routes.soap_routes import router as soap_router
from backend.routes.drug_routes import router as drug_router

app = FastAPI(
    title="DermaCare AI",
    description="Offline Dermatology Clinical Decision Support",
    version="0.1"
)

# Add CORS middleware to allow a frontend to access this backend later locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Can be locked down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagnosis_router)
app.include_router(soap_router)
app.include_router(drug_router)

# Healthcheck home route
@app.get("/")
def home():
    return {"status": "ok", "message": "DermaCare AI Engine Running"}
