# DermaCare AI - Oracle Cloud Deployment Guide

Deploy DermaCare AI to Oracle Cloud Always Free tier for multi-clinic production use.

## Prerequisites

- Oracle Cloud Free Tier account (no credit card required)
- SSH key for connecting to the instance
- Domain name (optional, for production SSL)

---

## Step 1: Create Oracle Cloud Account

1. Go to [cloud.oracle.com](https://cloud.oracle.com)
2. Click "Start for free"
3. Sign up with email, password, and phone number
4. Verify email and complete identity verification
5. **No credit card required** for Always Free tier

---

## Step 2: Create Compute Instance

1. Log into Oracle Cloud Console
2. Navigate to: **Compute → Instances**
3. Click **Create Instance**

### Instance Configuration

| Setting | Value |
|---------|-------|
| Name | `dermacare-ai` |
| Compartment | Root (or your compartment) |
| Placement | Automatic placement |
| Image | **Oracle Linux 8** (or Ubuntu 22.04) |
| Shape | **Ampere** (4 cores, 24GB RAM) - Always Free eligible |

### Networking

| Setting | Value |
|---------|-------|
| Virtual cloud network | Create new |
| Subnet | Create in public subnet |
| Assign public IPv4 address | **Yes** |

### SSH Keys

1. Generate SSH key locally:
   ```bash
   # Windows PowerShell or Git Bash
   ssh-keygen -t ed25519 -C "dermacare" -f ~/.ssh/dermacare_key
   
   # For Windows, also create .ppk if using PuTTY
   ```
2. Upload the **public key** (`.pub` file) to Oracle

3. Save the **private key** securely on your local machine

### Create Instance

Click **Create** and wait 2-3 minutes for provisioning.

---

## Step 3: Configure Firewall

### Oracle Cloud Security List

1. Navigate to: **Networking → Virtual Cloud Networks → Your VCN**
2. Click **Security Lists → Default Security List**
3. Add Ingress Rules:

| Type | Source | Ports |
|------|--------|-------|
| CIDR | 0.0.0.0/0 | 80 (HTTP) |
| CIDR | 0.0.0.0/0 | 443 (HTTPS) |
| CIDR | 0.0.0.0/0 | 8000 (API) |
| CIDR | 0.0.0.0/0 | 22 (SSH) |

### Instance Firewall (Oracle Linux)

```bash
# SSH into your instance
ssh -i ~/.ssh/dermacare_key opc@<YOUR_PUBLIC_IP>

# Configure firewall
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Or for Ubuntu:
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
```

---

## Step 4: Install Dependencies

### Update System

```bash
# Oracle Linux / CentOS
sudo dnf update -y

# Ubuntu
sudo apt update && sudo apt upgrade -y
```

### Install Docker

```bash
# Oracle Linux
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker opc

# Ubuntu
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker opc
```

### Install Docker Compose

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**Log out and back in for group changes to take effect.**

---

## Step 5: Clone and Configure Project

### Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone your repository (adjust URL)
git clone https://github.com/yourusername/dermacare-ai.git
cd dermacare-ai
```

### Create Environment File

```bash
cp .env.production.example .env.production
nano .env.production
```

Edit with your settings:

```env
SECRET_KEY=generate-a-secure-random-key-here
DATABASE_URL=postgresql://dermacare:your_password@localhost:5432/dermacare
OLLAMA_BASE_URL=http://localhost:11434
CORS_ORIGINS=http://your-public-ip:3000
```

### Create PostgreSQL Password

```bash
# Generate secure password
openssl rand -base64 24
```

---

## Step 6: Set Up PostgreSQL

### Option A: Use Docker (Recommended)

```bash
# Create Docker network
docker network create dermacare-net

# Create PostgreSQL container
docker run -d \
  --name dermacare-postgres \
  --network dermacare-net \
  -e POSTGRES_DB=dermacare \
  -e POSTGRES_USER=dermacare \
  -e POSTGRES_PASSWORD=your_secure_password \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:15-alpine

# Verify
docker logs dermacare-postgres
```

### Option B: Native PostgreSQL (Oracle Linux)

```bash
sudo dnf module enable postgresql:15
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Configure PostgreSQL
sudo -u postgres psql << 'EOF'
CREATE DATABASE dermacare;
CREATE USER dermacare WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE dermacare TO dermacare;
EOF
```

---

## Step 7: Deploy Application

### Using Docker Compose

```bash
# Build and start
docker-compose -f docker-compose.yml up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Manual Deployment

```bash
# Build Docker image
docker build -t dermacare-ai:latest .

# Run container
docker run -d \
  --name dermacare-api \
  --network dermacare-net \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://dermacare:password@dermacare-postgres:5432/dermacare \
  -e SECRET_KEY=your-secret-key \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  --restart unless-stopped \
  dermacare-ai:latest
```

---

## Step 8: Configure Ollama at Each Clinic

Ollama runs **locally at each clinic**, not on Oracle Cloud.

### Clinic Setup

```bash
# Install Ollama (on clinic workstation/server)
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull phi3:3.8b

# Start Ollama service
ollama serve
```

### Network Configuration

Each clinic configures their local IP in the frontend:
```javascript
// In frontend app.js
const API_BASE = 'http://clinic-local-server:8000';
```

---

## Step 9: Verify Deployment

### Test API

```bash
# Health check
curl http://localhost:8000/health

# Login (default admin)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@dermacare.local","password":"your-password"}'
```

### Access Frontend

1. Serve static files:
   ```bash
   # From project directory
   cd frontend
   python3 -m http.server 3000
   ```

2. Open browser: `http://<YOUR_PUBLIC_IP>:3000`

---

## Step 10: Set Up Backups (Optional)

### Oracle Object Storage

1. Create Object Storage namespace:
   - Go to **Storage → Object Storage → Namespaces**
   - Note your namespace

2. Create bucket:
   - Go to **Storage → Object Storage → Buckets**
   - Create bucket: `dermacare-backups`

3. Generate S3 Credentials:
   - Go to **Identity → Users → Your User**
   - Click **S3 Credentials → Create Secret Key**
   - Save Access Key and Secret Key

### Configure Backup Script

```bash
# Edit backup.sh
nano backup.sh

# Add credentials
export S3_ENDPOINT=https://your-namespace.compat.objectstorage.us-region-1.oraclecloud.com
export S3_ACCESS_KEY=your-access-key
export S3_SECRET_KEY=your-secret-key
export S3_BUCKET_NAME=dermacare-backups
```

### Schedule Daily Backups

```bash
# Add to crontab
crontab -e

# Run daily at 2 AM
0 2 * * * /home/opc/dermacare-ai/backup.sh >> /home/opc/backup.log 2>&1
```

---

## SSL/HTTPS Configuration (Optional)

### For Domain Name Setup

1. Install Nginx:
   ```bash
   sudo dnf install -y nginx
   sudo systemctl start nginx
   ```

2. Get SSL Certificate (Let's Encrypt):
   ```bash
   sudo dnf install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

3. Update Nginx config with provided `deploy/nginx.conf`

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Common issues:
# - DATABASE_URL incorrect
# - Port already in use
# - PostgreSQL not ready (wait 30s)
```

### Database Connection Failed

```bash
# Check PostgreSQL
docker exec -it dermacare-postgres psql -U dermacare -d dermacare

# Test connection
docker exec -it dermacare-api sh -c "nc -zv dermacare-postgres 5432"
```

### Ollama Not Connecting

```bash
# Check Ollama service
curl http://localhost:11434/api/tags

# For remote Ollama, ensure firewall allows port 11434
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Oracle Cloud Ampere has 4 cores, 24GB RAM
# Should handle 100+ concurrent users easily
```

---

## Maintenance

### Update Application

```bash
cd ~/dermacare-ai
git pull origin main
docker-compose down
docker-compose up -d --build
```

### Database Backup

```bash
# Manual backup
docker exec dermacare-postgres pg_dump -U dermacare dermacare > backup.sql

# Restore
docker exec -i dermacare-postgres psql -U dermacare dermacare < backup.sql
```

### View Logs

```bash
# All containers
docker-compose logs -f

# Specific service
docker-compose logs -f api
```

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    ORACLE CLOUD VM                          │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │    Nginx     │───▶│   FastAPI    │───▶│  PostgreSQL  │  │
│  │   :80/:443   │    │    :8000    │    │    :5432     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Oracle Object Storage (Backups)           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │ Clinic A │        │ Clinic B │        │ Clinic C │
   │ Ollama   │        │ Ollama   │        │ Ollama   │
   │ (Local)  │        │ (Local)  │        │ (Local)  │
   └──────────┘        └──────────┘        └──────────┘
```

---

## Support

For issues, check:
1. Docker logs: `docker-compose logs`
2. Application logs in `/var/log/dermacare/`
3. Oracle Cloud Console for instance health
