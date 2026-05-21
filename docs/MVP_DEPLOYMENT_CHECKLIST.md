# MVP Deployment Sanity Checklist - DermaCare AI

This checklist serves as your post-deployment operational validation sweep. Run through these checks in order to verify that all layers of the secure hybrid architecture (Vercel static client ➔ Koyeb FastAPI ➔ Cloudflare Tunnel ➔ Local GPU) are synchronized, secure, and operational.

---

## 1. Local Workstation & Tunnel Verification
Verify that your local workstation is correctly hosting the inference model and routing requests safely.

- [ ] **Ollama Server Status**:
  - Run `curl http://localhost:11434` locally.
  - **Expected Result**: Returns `"Ollama is running"`.
- [ ] **Model Registry**:
  - Run `ollama list` in terminal.
  - **Expected Result**: Confirm `phi3:latest` (or your configured `OLLAMA_MODEL`) is installed locally.
- [ ] **Cloudflare Tunnel Service**:
  - Run `Get-Service -Name "cloudflared"` in Administrator PowerShell.
  - **Expected Result**: `Status` is `Running` and `StartType` is `Automatic`.
- [ ] **Public Tunnel Resolution**:
  - From a smartphone, secondary PC, or external network, browse to: `https://ollama-secure-9x8f2a.yourdomain.com/` (replace with your secure CNAME).
  - **Expected Result**: Returns `"Ollama is running"` securely over HTTPS.
- [ ] **Network Binding Lock**:
  - Verify that the Windows environment variable `OLLAMA_HOST` is **not** set to `0.0.0.0`.
  - **Expected Result**: Socket is bound only to loopback (`127.0.0.1`), ensuring the machine is locked down from local LAN threats.

---

## 2. Koyeb Backend API Verification
Verify that the FastAPI backend server has booted successfully and has linked with your tunnel.

- [ ] **Container Boot State**:
  - Inspect the Koyeb Service Dashboard.
  - **Expected Result**: Status is listed as **Healthy** (health check route `/health` passed).
- [ ] **Environment Verification**:
  - Confirm `OLLAMA_BASE_URL` contains the secure HTTPS tunnel domain.
  - Confirm `SECRET_KEY` is set to a long, secure random key.
- [ ] **Public Health Endpoint**:
  - Navigate to: `https://your-backend-api.koyeb.app/health`.
  - **Expected Result**: Yields JSON `{"status": "ok"}` instantly.
- [ ] **SSL Security**:
  - Verify that the URL uses `https://`.
  - **Expected Result**: Browser indicates a secure connection with a valid SSL/TLS certificate.

---

## 3. Vercel PWA Client Verification
Verify that the static frontend client loads perfectly and registers the service workers.

- [ ] **Initial Page Load**:
  - Navigate to your Vercel address: `https://your-frontend.vercel.app`.
  - **Expected Result**: Page loads in under 1 second, showing the modern clinician login page.
- [ ] **PWA Service Worker Registration**:
  - Open Chrome DevTools (`F12`), go to **Application** tab, and click **Service Workers**.
  - **Expected Result**: Service worker is listed as active and running (`service-worker.js`).
- [ ] **Local Storage Settings Sync**:
  - Navigate to **Settings** screen, configure your Koyeb Backend URL, and click **Save Settings**.
  - **Expected Result**: Toast notification confirms settings saved, and `localStorage` key `dermacare_backend_url` is updated.
- [ ] **Connection Badge State**:
  - Verify the status indicator in the main Workspace header.
  - **Expected Result**: Shows a green status indicator: **`Connected`**.

---

## 4. End-to-End Clinical Flow Verification
Verify that the full diagnostic and reasoning chain executes correctly through the secure tunnel and local GPU.

- [ ] **Clinician Registration**:
  - On the frontend login screen, click **Create Account**.
  - Enter a valid email and password, then submit.
  - **Expected Result**: Account is created and user is routed to the login page.
- [ ] **Clinician Login**:
  - Log in with the newly created clinician credentials.
  - **Expected Result**: Credentials authenticate successfully, a secure JWT token is saved, and you are routed to the Practice Dashboard.
- [ ] **Intake & Scan Submission**:
  - Click **New Diagnosis**.
  - Submit the following clinical baseline data:
    - **Complaint**: `"Dry, thick, scaly plaques with silvery scales on both elbows."`
    - **Lesion**: `"Erythematous plaques with clear borders."`
    - **Symptoms**: `"Pruritus, mild soreness, worse during winter."`
    - **Age**: `42`
    - **Region**: `"North America"`
  - Click **Submit Clinical Analysis**.
- [ ] **GPU Execution Monitoring**:
  - While processing, monitor task manager or CLI logs on the local workstation.
  - **Expected Result**: GPU utilization rises (VRAM offloading to RTX 4050 occurs).
- [ ] **Differential Resolution**:
  - Verify response time and diagnostic ranking.
  - **Expected Result**: Response returns in under 8 seconds. **Psoriasis** is ranked #1 with a detailed differential panel.
- [ ] **SOAP Generation Validation**:
  - Click **Generate SOAP Note** or navigate to Step 5.
  - **Expected Result**: Note is fully structured with clear Subjective, Objective, Assessment, and Plan fields.
- [ ] **Drug Checker Validation**:
  - Navigate to the **Drug Checker** tab.
  - Search for `"Methotrexate"` and `"Aspirin"`.
  - **Expected Result**: Displays interaction results, risk scoring, and clinical safety guidance without error.

---

## 5. Resiliency & Emergency Fallback Verification
Verify that the app degrades gracefully when parts of the hybrid network become unavailable.

- [ ] **Ollama Workstation Offline Simulation**:
  - Stop the `cloudflared` Windows Service temporarily.
  - Run a new diagnosis intake from your Vercel app.
  - **Expected Result**:
    - The API does not crash.
    - The system returns a high-confidence **Clinical Fallback Response**.
    - The UI presents a clean, non-disruptive warning that the primary AI model is temporarily offline, but clinical safety fallback rules remain active.
  - *Restart your `cloudflared` Windows Service after testing.*
- [ ] **Backend Offline Simulation**:
  - Disconnect your internet connection on the client computer.
  - Browse your Case History on the Vercel PWA.
  - **Expected Result**:
    - PWA loads immediately from cache.
    - Existing clinical history and cases can be viewed without errors (resolves via IndexedDB).
    - Status badge gracefully turns red: **`Offline`**.
