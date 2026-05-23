<div align="center">

# 🩺 DermaCare AI

### **AI-Powered Clinical Decision Support for Modern Dermatology**

[![Live MVP](https://img.shields.io/badge/Live%20MVP-Operational-00C9A7?style=for-the-badge)](https://dermacare-ai-inky.vercel.app)
[![Powered By Arogix AI](https://img.shields.io/badge/Powered%20By-Arogix%20AI-6C5CE7?style=for-the-badge)](mailto:arogixai@gmail.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/AI%20Engine-Ollama%20%2F%20Phi3-FF7675?style=for-the-badge)](https://ollama.ai/)
[![Deployment](https://img.shields.io/badge/Cloud%20Infrastructure-Oracle%20%2B%20Cloudflare-0984E3?style=for-the-badge)](#system-architecture)

*A sophisticated, clinician-assistive decision support platform designed to bring reliable, secure, and offline-resilient AI diagnostics to modern clinical workflows.*

---

[Live MVP Client](https://dermacare-ai-inky.vercel.app) • [System Architecture](#system-architecture) • [Clinical Safety](#clinical-safety) • [Developer Setup](#-quickstart-guide)

</div>

---

## 💎 Project Overview

**DermaCare AI** is an advanced, clinician-in-the-loop Clinical Decision Support System (CDSS) specifically engineered to elevate dermatological care in diverse environments—ranging from premium urban practices to resource-constrained clinics.

In dermatology, early triage and precise diagnostic mapping are critical. However, clinicians often face extreme caseloads, administrative friction, and fluctuating network reliability. DermaCare AI bridges this gap by acting as a highly intelligent, secure, and local-first clinical co-pilot. By leveraging state-of-the-art local Large Language Models (LLMs) alongside deterministic clinical enrichment pipelines, it helps clinicians formulate diagnostic hypotheses, generate structured SOAP documentation, and verify drug interactions—ensuring that patient data remains fully private, secure, and on-premises.

---

## 🌟 Core Platform Features

DermaCare AI delivers a suite of high-performance clinical tools built to fit naturally into existing healthcare workflows:

| Feature | Description | Clinical Impact |
| :--- | :--- | :--- |
| **🩺 AI Differential Diagnosis** | Generates a structured list of potential dermatological conditions, calibrated by Fitzpatrick skin phototypes. | Expands diagnostic coverage and highlights rare clinical variants. |
| **📝 SOAP Report Generation** | Automatically drafts standard Subjective, Objective, Assessment, and Plan notes based on patient consultations. | Eliminates hours of manual typing and structures reports for EMR compatibility. |
| **💊 Treatment Recommendation** | Outlines safe, localized care pathways, therapeutic ranges, and referral guidelines. | Accelerates care delivery and structures first-line patient plans. |
| **🔍 Drug Interaction Checker** | Cross-references proposed treatments with existing patient medications to flag warnings. | Prevents adverse reactions and ensures clinical prescribing safety. |
| **📊 Clinical Confidence Analysis** | Employs advanced Monte Carlo dropout emulation to present transparent confidence intervals. | Protects clinicians from LLM hallucinations by showing model certainty limits. |
| **🛡️ Dynamic Safeguard & Fallbacks** | Automatically executes schema-repair loops and falls back to robust schemas when needed. | Guarantees operational uptime and consistent user-interface rendering. |
| **⚡ Hybrid AI Inference** | Seamlessly alternates between high-throughput cloud LLMs (Groq) and local secure engines (Ollama). | Provides unparalleled speed and guarantees offline functionality in low-connectivity zones. |

---

## 🌐 Live Interactive MVP

DermaCare AI is fully realized and operational. Our client application is deployed to production:

### 👉 **[Access the Live MVP: dermacare-ai-inky.vercel.app](https://dermacare-ai-inky.vercel.app)**

* **Operational Status**: `Active`
* **Network Status**: `Online`
* **Offline Resiliency**: Enabled (Progressive Web Application). Once loaded, the application caches core resources, allowing clinicians to view historical cases and perform mock testing completely offline.

---

## 🏗️ System Architecture

DermaCare AI utilizes a secure, hybrid, decentralized architecture. By separating the static, client-side application from the inference layers, the platform achieves extreme scalability while maintaining local clinical data sovereignty.

```
                  ┌────────────────────────────────────────┐
                  │       Vercel Static Edge (PWA)         │
                  │   - Global HTML/CSS/JS Delivery        │
                  │   - Local Patient History (IndexedDB)  │
                  └──────────────────┬─────────────────────┘
                                     │
                                     │ Secure CORS HTTPS Requests
                                     ▼
                  ┌────────────────────────────────────────┐
                  │       FastAPI Backend API VM           │
                  │   - JWT Auth & Token Verification      │
                  │   - Cache Management & Logging         │
                  │   - Structured Output Validation Gates │
                  └──────┬──────────────────────────┬──────┘
                         │                          │
          (Online Path)  │                          │  (Secure Hybrid Path)
      ┌──────────────────┘                          └──────────────────┐
      ▼                                                                ▼
┌───────────┐                                                ┌──────────────────┐
│ Groq API  │                                                │Cloudflare Tunnel │
│ (Cloud)   │                                                └─────────┬────────┘
└───────────┘                                                          │
                                                                       ▼
                                                             ┌──────────────────┐
                                                             │Local Workstation │
                                                             │- RTX 4050 GPU    │
                                                             │- Ollama Daemon   │
                                                             │- Local Phi3      │
                                                             └──────────────────┘
```

### Technical Blueprint:
1. **Frontend App (Vercel)**: Delivered instantly via Vercel's global edge network. Implemented as a clean, responsive Vanilla JavaScript Progressive Web Application (PWA) using IndexedDB for zero-latency local caching.
2. **Backend Engine (FastAPI)**: Hosted on a high-availability server layer. Manages request validation, JWT authentication, rate limiting, and dynamic schema repairs.
3. **AI Inference Layer (Ollama + Groq)**: Supports double-redundancy. Heavy diagnostic inference runs on local GPU workstations via secure **Cloudflare Tunnels**, while high-speed cloud-based fallback uses **Groq** APIs.
4. **Cloud Infrastructure (Oracle Cloud + Cloudflare)**: Oracle Cloud acts as our production database and routing hub, while Cloudflare Tunnels secure clinic-level hardware connections.

---

## 📸 Clinical Interface Walkthrough

DermaCare AI provides a premium, highly responsive user interface designed for maximum legibility in high-stress clinical environments:

<div align="center">

### **Drug Interaction & Clinical Safety Panel**
*Interactive checker showcasing active warnings and contraindications.*

![Drug Input Dashboard](file:///c:/Users/ragul/Music/dermacare-ai/assets/01_drug_input.png)

*Real-time alert engine highlighting serious, moderate, and mild therapeutic risks.*

![Interaction Verification Screen](file:///c:/Users/ragul/Music/dermacare-ai/assets/02_drug_result.png)

</div>

---

## 🛡️ Clinical Safety & Governance

DermaCare AI is engineered strictly as a **Clinical Decision Support System (CDSS)**. It operates under a clear, ethically designed medical safety model:

1. **Clinician-Assistive Design**: The system does **not** make direct, autonomous medical diagnoses. It outlines differentials, highlights clinical evidence, and guides the physician, who remains the sole legal and clinical authority.
2. **Monte Carlo Confidence Profiling**: Each diagnostic pass runs through an emulation pipeline that estimates confidence intervals. If uncertainty exceeds `LOW_CONFIDENCE_ESCALATION_THRESHOLD`, the system automatically embeds prominent warning prompts advising specialist referral.
3. **Deterministic Enrichment Overlay**: Raw AI outputs are dynamically verified against local clinical databases. First-line therapies (e.g., specific corticosteroid dosing, thick emollient schedules) are deterministically injected to ensure precise, guidelines-compliant clinical information.
4. **Data Sovereignty**: The platform is compliant-ready out of the box. Patient health details (PHI) are kept strictly local using secure local browser database structures (IndexedDB) or on-premises GPU infrastructure, eliminating cloud leak vectors.

---

## 💻 Elite Production Tech Stack

Our platform leverages a modern, highly optimized stack tailored for low latency and zero framework bloat:

* **FastAPI**: Extremely fast, asynchronous Python web framework used for API orchestration.
* **Ollama & Phi-3**: Local AI inference engine utilizing Microsoft's `phi3:3.8b` model for private clinical reasoning.
* **Groq API**: High-speed cloud-based inference provider used as a high-availability fallback.
* **Vercel**: Edge network provider for instantaneous frontend PWA asset delivery.
* **Oracle Cloud VMs**: Secure cloud hosting for dedicated PostgreSQL production database infrastructure.
* **Cloudflare Tunnels**: Zero-trust network tunneling securing on-premise clinic GPU nodes.
* **Vanilla JavaScript & CSS3**: Core frontend engineered with vanilla DOM-caching for speed, responsiveness, and zero package-bloat.
* **React & TailwindCSS Roadmap**: Enterprise dashboard templates built to integrate into clinical EMRs.

---

## 🚀 Quickstart Guide

Get DermaCare AI running in a development environment in under 5 minutes:

### 1. Clone the Codebase
```bash
git clone https://github.com/Ragulpriyan-Coder/DermaCare_AI.git
cd DermaCare_AI
```

### 2. Configure Environment
Copy the example configuration file:
```bash
cp .env.example .env
```
Ensure your `.env` contains the proper Ollama and Groq credentials:
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3
```

### 3. Spin Up Backend & Inference
```bash
# Setup Python virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Start FastAPI dev server
python -m uvicorn backend.app:app --reload
```

### 4. Serve the Frontend PWA
You can serve the static frontend directory using any static file server:
```bash
python -m http.server 3000 --directory frontend
```
Open **`http://localhost:3000`** in your browser to interact with the system.

---

## 🔮 Future Roadmap

DermaCare AI is continually expanding its clinical horizons. Our technical progression covers:

* **Enterprise Cloud GPU Balancing**: Autoscaling cluster orchestration to handle thousands of simultaneous clinic tunnels.
* **Multimodal Visual Inputs**: Integration of image classification models to analyze lesion photographs alongside text symptoms.
* **HL7 / FHIR Integration**: Direct connectivity adapters to synchronize SOAP reports and assessments with leading hospital EMR systems.
* **Clinic Analytics Dashboards**: Interactive, high-impact clinician panels presenting regional dermatological health analytics.
* **Consensus Multi-Model Engines**: Orchestrating multiple lightweight models (Phi3, Llama3, Qwen) to generate cross-validated clinical summaries.

---

## 🏢 Corporate Profile & Alliance

**DermaCare AI** is designed and maintained by **Arogix AI**. 

> "Building next-generation AI systems for healthcare, security, and advanced clinical decision support."

* **Corporate Branding**: Arogix AI Systems
* **Key Focus**: Secure local inference, offline-first clinical pipelines, and clinical transparency.
* **General Inquiries**: [arogixai@gmail.com](mailto:arogixai@gmail.com)
* **Alliance Opportunities**: Partner with us to scale local-first medical intelligence globally.

---

<div align="center">

*Disclaimer: DermaCare AI is designed for clinician-assistive purposes to guide differentials and clinical documentation. It is not an autonomous diagnostic system and must always be used in tandem with professional medical judgment.*

</div>
