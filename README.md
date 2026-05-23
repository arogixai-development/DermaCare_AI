# DermaCare AI 🩺
https://v0-dermacareai.vercel.app/
[![Offline First](https://img.shields.io/badge/Offline-First-blue.svg)](https://github.com/arogixai-development/DermaCare_AI)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-009688.svg)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/AI-Ollama%20(phi3)-orange.svg)](https://ollama.ai/)

DermaCare AI is an offline-first dermatology clinical decision support system (CDSS) specifically engineered for low-resource healthcare environments. By leveraging local AI inference, it provides high-quality diagnostic assistance and clinical documentation without requiring an active internet connection.

---

## 🌟 Key Features

- **Offline AI Diagnosis**: Perform high-accuracy dermatological assessments locally.
- **Clinical Reasoning**: Transparent AI explanations for suggested diagnoses.
- **SOAP Note Generation**: Automatically generate structured clinical notes (Subjective, Objective, Assessment, Plan).
- **Drug Interaction Checker**: Verify potential reactions between suggested treatments and existing medications.
- **Case History Storage**: Local persistence of patient cases via browser storage (IndexedDB).
- **PWA Support**: Installable as a Progressive Web App for a native-like experience on mobile and desktop.

---

## 🏗️ Architecture

The system is designed with a decoupled architecture to ensure robustness and privacy:

- **Frontend**: A high-performance Vanilla JavaScript application built as a PWA. It handles all UI logic, local storage, and service worker management.
- **Backend API**: A FastAPI service that acts as the orchestration layer between the frontend and the AI engine.
- **AI Engine**: Powered by **Ollama** running the **phi3** model. All inference is performed on the local machine, ensuring patient data never leaves the facility.

---

## 🚀 Installation

### Prerequisites

1. **Python 3.10+**
2. **Node.js** (for local development server, or any static server)
3. **Ollama**: [Download and install Ollama](https://ollama.ai/download)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ragulpriyan-Coder/DermaCare_AI.git
   cd DermaCare_AI
   ```

2. **Backend Setup**:
   ```bash
   # Create a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **AI Model Setup**:
   ```bash
   # Ensure Ollama is running, then pull the required model
   ollama pull phi3
   ```

4. **Environment Configuration**:
   ```bash
   # Copy the example environment file
   cp .env.example .env
   # Edit .env with your local settings if necessary
   ```

---

## 🛠️ Running the Project

### 1. Start the Backend
```bash
python -m uvicorn backend.app:app --reload
```
*The API will be accessible at `http://localhost:8000`.*

### 2. Start the Frontend
You can serve the `frontend` directory using any static web server.
Using Python:
```bash
cd frontend
python -m http.server 3000
```
*Open `http://localhost:3000` in your browser.*

---

## 📱 Demo Mode

DermaCare AI includes a demo mode for testing without a full backend setup. This allows developers to explore the UI and PWA features immediately. Toggle the demo mode in the application settings to use mocked AI responses.

---

## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

*Note: This tool is intended for clinical decision support and should be used by qualified healthcare professionals. It is not a substitute for professional medical judgment.*
