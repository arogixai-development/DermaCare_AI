# Cloudflare Tunnel Configuration Guide - DermaCare AI

This guide describes how to securely expose your local **Ollama RTX 4050 GPU Workstation** to the cloud-hosted **Koyeb FastAPI Backend API** using a secure, firewall-friendly **Cloudflare Tunnel** (`cloudflared`). 

With this architecture, **no public router ports are opened**, and your local machine is protected from direct internet scanning, as only authenticated connections via Cloudflare are routed to your local Ollama port (`11434`).

```
Koyeb Backend API (Cloud)
  │ (HTTPS encrypted)
  ▼
Cloudflare Edge Network
  │ (Secure Persistent gRPC Tunnel)
  ▼
cloudflared daemon (Running locally on Windows)
  │ (Localhost request)
  ▼
Ollama Server (Running on RTX 4050 Machine - localhost:11434)
```

---

## Prerequisites

1. A free **Cloudflare Account** ([signup.cloudflare.com](https://signup.cloudflare.com/)).
2. A **registered domain name** pointed to Cloudflare DNS nameservers.
3. An active local **Ollama** server running on your RTX 4050 GPU workstation.

---

## Step 1: Install `cloudflared` on Windows

You can install the Cloudflare Tunnel daemon (`cloudflared`) on Windows using Windows Package Manager (`winget`) or manual download.

### Option A: Via Winget (Recommended)
Open **PowerShell as Administrator** and execute:
```powershell
winget install cloudflare.cloudflared
```
*Restart your PowerShell session after installation to refresh path environment variables.*

### Option B: Direct Download
1. Download the latest MSI installer from the [Official Cloudflare Repository](https://github.com/cloudflare/cloudflared/releases).
2. Run the installer and complete the setup wizard.

### Verify Installation
Confirm `cloudflared` is correctly in your system path:
```powershell
cloudflared --version
```

---

## Step 2: Authenticate `cloudflared`

Associate the local daemon with your Cloudflare DNS account:

1. In PowerShell, run the login command:
   ```powershell
   cloudflared tunnel login
   ```
2. A browser window will open automatically. Log in to your Cloudflare account.
3. Select the domain you want to use for routing (e.g., `yourdomain.com`).
4. Click **Authorize**.
5. Once authorized, a certificates file (`cert.pem`) will be saved in your user directory: `C:\Users\<YourUsername>\.cloudflared\cert.pem`.

---

## Step 3: Create a Named Cloudflare Tunnel

Create the persistent tunnel that will connect to your local Ollama instance:

1. Run the tunnel creation command:
   ```powershell
   cloudflared tunnel create dermacare-ollama-tunnel
   ```
2. Save the output. It will contain:
   - The **Tunnel ID** (a long UUID, e.g., `a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6`).
   - The path to your generated credentials JSON file (e.g., `C:\Users\<YourUsername>\.cloudflared\a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6.json`).

> [!WARNING]
> Keep the credentials JSON file secure. It grants route authorization for your tunnel.

---

## Step 4: Create the Tunnel Configuration File

Create a YAML configuration file to instruct `cloudflared` how to route incoming traffic locally.

1. Navigate to your user's `.cloudflared` directory:
   ```powershell
   cd "$HOME\.cloudflared"
   ```
2. Create a new file named `config.yml` using Notepad or your favorite editor:
   ```powershell
   notepad config.yml
   ```
3. Paste the following configuration, replacing `<TUNNEL_ID>` and `<YourUsername>` with your actual values:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: C:\Users\<YourUsername>\.cloudflared\<TUNNEL_ID>.json

ingress:
  # Route a secure high-entropy subdomain to your local Ollama port
  - hostname: ollama-secure-9x8f2a.yourdomain.com
    service: http://localhost:11434
  
  # Catch-all rule: reject all other traffic with a 404
  - service: http_status:404
```

> [!TIP]
> **Security Best Practice**: Use a high-entropy, random subdomain prefix (e.g., `ollama-secure-9x8f2a`) instead of a generic `ollama` subdomain. This prevents scanners and unauthorized bots from discovering your Ollama endpoint.

---

## Step 5: Bind the DNS Route in Cloudflare

Create a DNS CNAME record that routes internet traffic targeting your secure hostname through the tunnel.

Run the following command:
```powershell
cloudflared tunnel route dns dermacare-ollama-tunnel ollama-secure-9x8f2a.yourdomain.com
```

*Verify in your Cloudflare Web Dashboard under DNS Settings that a CNAME record has been created pointing `ollama-secure-9x8f2a` to `<TUNNEL_ID>.cfargotunnel.com`.*

---

## Step 6: Test the Tunnel Connection

Run the tunnel in foreground mode to verify everything boots, connects, and resolves correctly:

```powershell
cloudflared --config C:\Users\<YourUsername>\.cloudflared\config.yml tunnel run dermacare-ollama-tunnel
```

Watch the terminal console logs. You should see successful connection states:
```text
2026-05-21T12:45:00Z INF Connection a1b2c3d4-... registered connIndex=0 ip=198.41.200.193 location=MIA
2026-05-21T12:45:01Z INF Connection a1b2c3d4-... registered connIndex=1 ip=198.41.192.167 location=MIA
```

### Validate Live Resolution
While the tunnel is running, open a browser or terminal window on a separate device and make a GET request:
```bash
curl https://ollama-secure-9x8f2a.yourdomain.com/
```
**Expected Response**:
```text
Ollama is running
```
If you get this response, your tunnel is fully functional and routing safely! Press `Ctrl + C` in PowerShell to stop the foreground tunnel.

---

## Step 7: Install as a Persistent Windows Service

To ensure the tunnel starts automatically when the workstation boots (without needing an active user session), run it as a standard Windows Service:

1. Open **PowerShell as Administrator**.
2. Install the service:
   ```powershell
   cloudflared --config C:\Users\<YourUsername>\.cloudflared\config.yml service install
   ```
3. Start the service:
   ```powershell
   Start-Service -Name "cloudflared"
   ```
4. Verify the service is running and configured for automatic startup:
   ```powershell
   Get-Service -Name "cloudflared" | Select-Object Name, Status, StartType
   ```

*Now, even if your local workstation restarts due to updates, the Cloudflare Tunnel daemon will boot automatically in the background, keeping Ollama exposed to Koyeb.*

---

## Step 8: Network Binding Security Lock (Critical)

Ensure Ollama is ONLY listening on `localhost` (`127.0.0.1`) and not listening publicly on all local network interfaces (`0.0.0.0`). 

On Windows:
1. By default, the Windows Ollama client binds exclusively to `127.0.0.1:11434`.
2. Do **not** set the system-wide environment variable `OLLAMA_HOST` to `0.0.0.0`. Keep it empty or set to `127.0.0.1`.
3. The Cloudflare Tunnel running on the machine can access `localhost:11434` internally, while preventing other computers on your local Wi-Fi or LAN from reaching Ollama directly.
