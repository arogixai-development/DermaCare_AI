# MVP Deployment Guide - DermaCare AI

This guide describes how to deploy the **DermaCare AI Clinical Decision Support System** to production-ready public cloud environments using the secure hybrid architecture:

- **Frontend**: Deployed statically on **Vercel** (Free Tier PWA).
- **Backend API**: Deployed inside a Docker container on **Koyeb** (Free Instance Tier).
- **Inference Layer**: Exposes your local **RTX 4050 GPU Workstation** running Ollama to Koyeb via a secure **Cloudflare Tunnel**.

```
┌─────────────────────────────────┐
│     Vercel Static PWA (Client)  │
└────────────────┬────────────────┘
                 │
                 │ API Requests (CORS safe, SSL encrypted)
                 ▼
┌─────────────────────────────────┐
│     Koyeb FastAPI Docker (API)  │
└────────────────┬────────────────┘
                 │
                 │ Outbound requests (HTTPS)
                 ▼
┌─────────────────────────────────┐
│  Cloudflare Tunnel (Secure URL) │
└────────────────┬────────────────┘
                 │
                 │ Secure local socket routing
                 ▼
┌─────────────────────────────────┐
│  Local RTX 4050 GPU (Ollama)    │
└─────────────────────────────────┘
```

---

## Prerequisites

Before beginning, complete the **Cloudflare Tunnel Setup** described in `docs/CLOUDFLARE_TUNNEL_SETUP.md` and ensure your local Ollama workstation is online, tunneling, and resolving successfully.

You will also need:
1. A **GitHub Account** containing a copy of the `DermaCare_AI` repository.
2. A free **Koyeb Account** ([koyeb.com](https://www.koyeb.com/)).
3. A free **Vercel Account** ([vercel.com](https://vercel.com/)).

---

## Phase 1: Deploy the Backend API on Koyeb

Koyeb is a highly performant cloud provider that builds and hosts Docker containers directly from Git. Since we have configured dynamic port-binding (`PORT` env variable) in our Dockerfile, deployment is seamless.

### Step 1: Connect GitHub to Koyeb
1. Log in to the [Koyeb Console](https://app.koyeb.com/).
2. Select **Create Service**.
3. Under **Deployment Method**, select **GitHub**.
4. Authorize Koyeb to access your GitHub repositories and select `DermaCare_AI`.

### Step 2: Configure Service Settings
Specify how Koyeb should build and host your API:

| Configuration | Value | Rationale |
| :--- | :--- | :--- |
| **Repository Branch** | `main` | Production branch |
| **Build Builder** | **Docker** | Uses the optimized `Dockerfile` in the root folder |
| **Port** | `8000` | Internally mapped port (Koyeb handles SSL routing) |
| **Instance Size** | `Eco (Micro)` | Fits fully within the free tier allowance |
| **Region** | Select closest to your local workstation | Minimizes latency between Koyeb and local GPU |

### Step 3: Define Environment Variables
Click **Add Environment Variable** to add the required production configurations:

| Key | Value (Example) | Rationale |
| :--- | :--- | :--- |
| `SECRET_KEY` | `your-high-entropy-jwt-secret-string` | Used to encrypt JWT authentication tokens |
| `OLLAMA_BASE_URL` | `https://ollama-secure-9x8f2a.yourdomain.com` | The HTTPS address of your Cloudflare Tunnel |
| `OLLAMA_MODEL` | `phi3` | Default clinical inference model |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Restricts API access exclusively to your Vercel app |

> [!TIP]
> Keep `CORS_ORIGINS` set to `*` for initial validation, but update it to your explicit Vercel frontend URL once deployed to secure your backend against cross-origin scripts.

### Step 4: Launch Backend
1. Click **Deploy**.
2. Koyeb will pull the codebase, parse the `Dockerfile`, compile your python environment, and deploy the service.
3. Wait 2-3 minutes. Once the health check passes, you will see a green **Healthy** status.
4. Copy the public URL provided by Koyeb (e.g., `https://dermacare-api-xxxx.koyeb.app`).

---

## Phase 2: Deploy the PWA Frontend on Vercel

Vercel provides instant static asset delivery with global edge caching, making it perfect for our lightweight Vanilla JavaScript frontend.

### Step 1: Import Repository
1. Log in to the [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New** and select **Project**.
3. Import the `DermaCare_AI` repository from your connected GitHub account.

### Step 2: Configure Build Settings (Critical)
Because our frontend is contained inside a dedicated subfolder, configure Vercel as follows:

1. **Framework Preset**: Select **Other**.
2. **Root Directory**: Click Edit, select the `frontend` directory, and click **Continue**.
3. **Build and Output Settings**:
   - **Build Command**: *Leave blank / default* (there is no build step).
   - **Output Directory**: *Leave blank / default* (it will serve static HTML/CSS/JS directly).

### Step 3: Launch Frontend
1. Click **Deploy**.
2. Vercel will upload and cache the PWA assets. Within 30 seconds, your site will be live!
3. Copy your live Vercel frontend address (e.g., `https://dermacare-ai.vercel.app`).

---

## Phase 3: Bind Frontend to Backend

Now that both services are running independently in the cloud, let's configure the frontend client to connect to your Koyeb API.

### Step 1: Access Settings Panel
1. Open your live Vercel frontend URL in a modern web browser.
2. In the left navigation sidebar, click on **Settings** (`nav-settings`).

### Step 2: Save Production API Endpoint
1. Locate the **Backend API URL** input field.
2. Replace `http://127.0.0.1:8000` with your live Koyeb API address (e.g., `https://dermacare-api-xxxx.koyeb.app`).
3. (Optional) Under **Local Ollama URL**, confirm it matches your local network configurations if running offline syncs.
4. Click **Save Settings**. The frontend will redirect you to the dashboard.

### Step 3: Validate Connection
1. Observe the **Connection Status** badge located in the top-bar header.
2. It should immediately resolve to green and show: **`Connected`**.
3. To perform a manual test:
   - Go to Settings.
   - Click **Test Connection**.
   - You should see a success toast: **`Backend connection OK`**.

---

## Phase 4: Production Security Hardening

Once you confirm the end-to-end loop is fully functional, complete the following security configurations:

1. **Restrict Backend CORS**:
   - Return to the Koyeb Console.
   - Edit your Backend Service.
   - Update the `CORS_ORIGINS` environment variable from `*` to your exact Vercel frontend URL (e.g., `https://dermacare-ai.vercel.app`).
   - Save and redeploy. This locks your backend to only accept clinical commands from your official PWA client.
2. **Check PWA Registration**:
   - Open Chrome DevTools (`F12`), navigate to the **Application** tab, and verify **Service Workers** are registered. This ensures offline-first caching works perfectly in clinics with unstable internet connectivity.
