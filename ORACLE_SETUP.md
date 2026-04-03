# Oracle Cloud Always Free Setup Guide

Step-by-step instructions for setting up Oracle Cloud Free Tier for DermaCare AI.

---

## Account Creation

### 1. Sign Up for Oracle Cloud

1. Visit [cloud.oracle.com](https://cloud.oracle.com)
2. Click **Start for free**
3. Choose **Sign up with a cloud account**
4. Enter:
   - Email address
   - Password
   - Confirm password
5. Click **Create Account**

### 2. Verify Email

1. Check your email for verification message from Oracle
2. Click the verification link
3. Complete the verification process

### 3. Complete Identity Verification

1. Enter your phone number for SMS verification
2. Enter the verification code
3. Oracle may require additional identity verification

### 4. Accept Terms and Activate

1. Read and accept Oracle Cloud Free Tier terms
2. Click **Activate**
3. **No credit card required** - this is the Always Free tier

---

## Dashboard Overview

After logging in, you'll see the Oracle Cloud Console:

```
┌─────────────────────────────────────────────────────────────┐
│ Oracle Cloud Infrastructure                          🔔 👤 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ☰ Menu                                                     │
│  ┌─────────────┐                                            │
│  │ Compute     │  ← Create and manage instances             │
│  │ Networking  │  ← Configure VCN, security rules           │
│  │ Storage     │  ← Object storage for backups              │
│  │ Databases   │  ← Can use Autonomous DB (Always Free)     │
│  │ Identity    │  ← Users, S3 credentials                   │
│  └─────────────┘                                            │
│                                                             │
│  Always Free Resources                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2 AMD Compute instances (1GB RAM each)               │   │
│  │ 1 Ampere Compute instance (4 cores, 24GB RAM)       │   │
│  │ 200GB Block storage                                 │   │
│  │ 10GB Object storage                                 │   │
│  │ 2 Autonomous Databases                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Creating Your First Compute Instance

### Step 1: Navigate to Compute

1. Click the **hamburger menu** (☰)
2. Select **Compute** → **Instances**

### Step 2: Create Instance

1. Click **Create Instance**

### Step 3: Configure Instance Details

```
Name: dermacare-ai
Compartment: (select your root compartment)
```

### Step 4: Placement

```
Availability Domain: AD 1 (or any available)
```

### Step 5: Image and Shape

**Choose an Image:**

| OS | Recommended |
|----|-------------|
| Oracle Linux 8 | ✓ Default, optimized |
| Ubuntu 22.04 | If preferred |
| CentOS 7 | Legacy support |

**Choose a Shape:**

1. Click **Change Shape**
2. Select **Ampere** tab
3. Choose **VM.Standard.A1.Flex** (4 cores, 24GB RAM)
   - This is Always Free eligible!

```
Shape: VM.Standard.A1.Flex
OCPU Count: 4
Memory (GB): 24
```

### Step 6: Networking

```
Virtual cloud network: Create new
Subnet: Create new public subnet
Assign a public IPv4 address: ✓ Yes
```

### Step 7: Add SSH Keys

**Generate SSH Key (on your local machine):**

```bash
# Windows PowerShell or Git Bash
ssh-keygen -t ed25519 -C "dermacare" -f $HOME/.ssh/dermacare_key

# View public key
cat $HOME/.ssh/dermacare_key.pub
```

**In Oracle Console:**

```
SSH keys: Save public key(s)
Paste public key: (paste the contents of dermacare_key.pub)
```

### Step 8: Boot Volume (Leave Default)

```
Boot volume: Leave default settings (50GB included free)
```

### Step 9: Review and Create

1. Review all settings
2. Click **Create**

Wait 2-3 minutes for provisioning.

---

## Getting Your Instance Public IP

After instance is created:

1. Go to **Compute** → **Instances**
2. Click on your instance `dermacare-ai`
3. Copy the **Public IP Address**

```
Example: 123.45.67.89
```

---

## Connecting via SSH

### Windows (PowerShell/Git Bash)

```bash
ssh -i ~/.ssh/dermacare_key opc@123.45.67.89
```

### First Connection

When you connect for the first time:

```
The authenticity of host '123.45.67.89' can't be established.
ECDSA key fingerprint is SHA256:xxxxx.
Are you sure you want to continue connecting (yes/no)?
```

Type `yes` and press Enter.

### Successful Connection

```
[opc@dermacare-ai ~]$
```

---

## Configuring Firewall Rules

### Step 1: Find Your Security List

1. In Oracle Console, go to your VCN
2. Click **Security Lists**
3. Click **Default Security List**

### Step 2: Add Ingress Rules

Click **Add Ingress Rules**:

| Rule 1 - HTTP | |
|---------------|---|
| Source Type | CIDR |
| Source CIDR | 0.0.0.0/0 |
| IP Protocol | TCP |
| Destination Port Range | 80 |
| Description | HTTP for DermaCare AI |

| Rule 2 - HTTPS | |
|----------------|---|
| Source Type | CIDR |
| Source CIDR | 0.0.0.0/0 |
| IP Protocol | TCP |
| Destination Port Range | 443 |
| Description | HTTPS for DermaCare AI |

| Rule 3 - API | |
|---------------|---|
| Source Type | CIDR |
| Source CIDR | 0.0.0.0/0 |
| IP Protocol | TCP |
| Destination Port Range | 8000 |
| Description | FastAPI Backend |

| Rule 4 - SSH | |
|---------------|---|
| Source Type | CIDR |
| Source CIDR | Your home IP (optional) |
| IP Protocol | TCP |
| Destination Port Range | 22 |
| Description | SSH Access |

### Step 3: Configure Instance Firewall

```bash
# For Oracle Linux
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

---

## Setting Up Object Storage (For Backups)

### Step 1: Create Object Storage Bucket

1. Go to **Storage** → **Object Storage & Archive Storage**
2. Select your compartment
3. Click **Create Bucket**

```
Bucket Name: dermacare-backups
Storage Tier: Standard
```

### Step 2: Get Namespace

1. Click **Namespace** at the top of the page
2. Copy and save your namespace

### Step 3: Generate S3 Credentials

1. Go to **Identity & Security** → **Users**
2. Click on your username
3. Click **S3 Credentials** in the left menu
4. Click **Create Secret Key**

```
Description: dermacare-backup-access
```

5. Copy and save:
   - **Access Key**
   - **Secret Key**

⚠️ **Important**: This is the only time you can see the Secret Key!

---

## Instance Setup (Commands to Run)

After SSH into your instance, run these commands:

### 1. Update System

```bash
# Oracle Linux
sudo dnf update -y

# Ubuntu
sudo apt update && sudo apt upgrade -y
```

### 2. Install Required Packages

```bash
# Oracle Linux
sudo dnf install -y git docker docker-compose curl

# Ubuntu
sudo apt install -y git docker.io docker-compose curl
```

### 3. Enable and Start Docker

```bash
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker opc
```

### 4. Download Docker Compose

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker-compose --version
```

### 5. Log Out and Back In

```bash
exit
ssh -i ~/.ssh/dermacare_key opc@123.45.67.89
```

### 6. Clone Your Project

```bash
cd ~
git clone https://github.com/yourusername/dermacare-ai.git
cd dermacare-ai
```

---

## Verify Setup

### Check Docker

```bash
docker --version
docker-compose --version
docker ps
```

### Check Resources

```bash
# Check CPU (should show 4 cores)
nproc

# Check Memory (should show ~24GB)
free -h

# Check Disk
df -h
```

---

## Common Issues

### "No route to host"

```bash
# Check security list rules in Oracle Console
# Verify firewall on instance
sudo firewall-cmd --list-all
```

### "Connection refused"

```bash
# Check if service is running
sudo systemctl status docker

# Check port is listening
sudo netstat -tlnp | grep 8000
```

### SSH Key Permission Error

```bash
# Fix key permissions (Windows Git Bash)
chmod 600 ~/.ssh/dermacare_key

# Or on Windows with PowerShell
icacls $HOME/.ssh/dermacare_key /inheritance:r /grant:r "$env:USERNAME:R"
```

---

## Next Steps

After completing this setup:

1. Continue to [DEPLOYMENT.md](./DEPLOYMENT.md) for deploying the application
2. Configure PostgreSQL and run the application
3. Set up automated backups to Object Storage

---

## Resource Limits (Always Free)

| Resource | Limit | Notes |
|----------|-------|-------|
| Ampere Instance | 1 | 4 cores, 24GB RAM |
| Block Storage | 200GB | Expandable |
| Object Storage | 10GB | For backups |
| Outbound Traffic | 10TB/month | Very generous |

Your DermaCare AI deployment is now ready for production use!
