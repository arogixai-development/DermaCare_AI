# DermaCare AI - Render Deployment Guide

Deploy DermaCare AI to Render for production use with PostgreSQL.

---

## Prerequisites

- GitHub account with DermaCare AI repository
- Render account (free tier available)

---

## Step 1: Create Render Account

1. Go to [render.com](https://render.com)
2. Click **Sign Up**
3. Connect with GitHub (recommended) or email
4. Verify your email

---

## Step 2: Create PostgreSQL Database

### Create Database

1. Log into Render Dashboard
2. Click **New +** → **PostgreSQL**

### Configure Database

| Setting | Value |
|---------|-------|
| Name | `dermacare-db` |
| Database | `dermacare` |
| User | `dermacare` |
| Plan | **Free** (500MB storage) |

### Get Connection String

1. Wait for database to provision (~2 minutes)
2. Click on your database
3. Scroll to **"External Database URL"**
4. Copy the connection string

```
Format: postgresql://dermacare:xxxxx@xxxxx.compute-1.amazonaws.com:5432/dermacare
```

**Important**: Save this connection string - you'll use it for your backend.

---

## Step 3: Create Backend Service

### Create Web Service

1. Click **New +** → **Web Service**

### Connect GitHub

1. Find your `dermacare-ai` repository
2. Click **Connect**

### Configure Service

| Setting | Value |
|---------|-------|
| Name | `dermacare-api` |
| Region | Choose closest to you |
| Branch | `main` |
| Root Directory | (leave empty) |
| Runtime | **Docker** |
| Plan | **Free** |

### Build Command

```bash
# Leave empty - uses Dockerfile
```

### Start Command

```bash
# Leave empty - uses CMD in Dockerfile
```

### Environment Variables

Click **Add Environment Variable** and add:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | (paste your PostgreSQL connection string) |
| `SECRET_KEY` | (generate a secure random string) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `CORS_ORIGINS` | `*` |
| `LOG_LEVEL` | `INFO` |

### Generate SECRET_KEY

Run this locally to generate a key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Health Check

Render will automatically detect the Dockerfile's HEALTHCHECK.

---

## Step 4: Deploy

1. Click **Create Web Service**
2. Wait for build (~5-10 minutes first time)
3. Monitor logs for errors

### Successful Deployment

You'll see:
```
✓ Service is live at https://dermacare-api.onrender.com
```

---

## Step 5: Configure Ollama (Per Clinic)

Since Ollama runs locally at each clinic, update the frontend to point to the local Ollama server.

### In frontend/app.js

```javascript
// Local clinic Ollama
const OLLAMA_BASE_URL = 'http://localhost:11434';

// Or point to a dedicated Ollama server
// const OLLAMA_BASE_URL = 'http://192.168.1.100:11434';
```

---

## Step 6: Set Up Frontend (Optional)

For production, serve the frontend from Render:

### Create Static Site

1. Click **New +** → **Static Site**

### Configure

| Setting | Value |
|---------|-------|
| Name | `dermacare-frontend` |
| GitHub | Connect `dermacare-ai` repo |
| Branch | `main` |
| Root Directory | `frontend` |
| Build Command | (leave empty) |
| Publish Directory | `.` |

### Environment Variables

| Key | Value |
|-----|-------|
| `API_BASE_URL` | `https://dermacare-api.onrender.com` |

---

## Step 7: Connect Backend to Frontend

### Update frontend/app.js

```javascript
// Point to your Render backend
const API_BASE = 'https://dermacare-api.onrender.com';
```

### Update CORS in Backend

In Render dashboard → your backend service → Environment:

```
CORS_ORIGINS=https://dermacare-frontend.onrender.com
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RENDER CLOUD                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Web Service (FastAPI)                                      │    │
│  │  dermacare-api.onrender.com                                │    │
│  │                                                              │    │
│  │  ┌──────────┐                                              │    │
│  │  │ FastAPI  │───▶ PostgreSQL (Render DB)                   │    │
│  │  │ :8000    │                                              │    │
│  │  └──────────┘                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Static Site (Frontend)                                     │    │
│  │  dermacare-frontend.onrender.com                           │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ Clinic A │       │ Clinic B │       │ Clinic C │
    │ Ollama   │       │ Ollama   │       │ Ollama   │
    │ (Local)  │       │ (Local)  │       │ (Local)  │
    └──────────┘       └──────────┘       └──────────┘
```

---

## Free Tier Limitations

| Resource | Limit |
|----------|-------|
| Web Service | Sleeps after 15 min inactivity |
| PostgreSQL | 500MB storage |
| Bandwidth | Limited |
| Custom Domain | ✅ Free |

### Avoid Sleep Mode

- Upgrade to **$7/month** plan to disable sleep
- Or use a **cron job** to ping the service every 15 minutes

### Cron Job to Prevent Sleep

```javascript
// Use a free cron service like cron-job.org
// Set to ping: https://dermacare-api.onrender.com/health
// Every 14 minutes
```

---

## Troubleshooting

### Build Fails

Check logs in Render dashboard for:
- Missing dependencies
- Environment variable errors
- Port configuration issues

### Database Connection Failed

1. Verify DATABASE_URL is correct
2. Check PostgreSQL is awake (Render free tier sleeps DB too)
3. Wait 30 seconds and retry

### CORS Errors

Update CORS_ORIGINS to include your frontend domain:
```
CORS_ORIGINS=https://dermacare-frontend.onrender.com
```

---

## Maintenance

### Update Application

1. Push changes to GitHub
2. Render auto-deploys on push to `main`

### Database Backups

Render provides automatic daily backups for PostgreSQL.

Manual backup:
```bash
pg_dump $DATABASE_URL > dermacare_backup.sql
```

---

## Cost Summary

| Service | Monthly Cost |
|---------|--------------|
| Web Service (Free) | $0 |
| PostgreSQL (Free) | $0 |
| Static Site (Free) | $0 |
| **Total** | **$0** |

Upgrade when needed:
- Web Service: $7/month (no sleep)
- PostgreSQL: $15/month (2GB, no sleep)

---

## Support

For Render issues: [render.com/docs](https://render.com/docs)
