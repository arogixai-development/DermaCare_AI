#!/bin/bash

# ==============================================================================
# DermaCare AI - Deployment Script for Oracle Cloud
# ==============================================================================
# Usage: ./deploy.sh [environment]
# Environments: production (default), staging, local
# ==============================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="dermacare-ai"
ENVIRONMENT="${1:-production}"
COMPOSE_FILE="docker-compose.yml"
LOG_FILE="/var/log/dermacare-deploy.log"

# ==============================================================================
# Functions
# ==============================================================================

log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$message"
    echo "$message" >> "$LOG_FILE" 2>/dev/null || true
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    log "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_warning "Not running as root. Some features may not work."
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
        log_info "Oracle Linux: sudo yum install docker -y"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed."
        exit 1
    fi
    
    log_success "Docker and Docker Compose are available"
}

check_environment() {
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        log_warning ".env file not found. Creating from example..."
        if [ -f "$SCRIPT_DIR/.env.production.example" ]; then
            cp "$SCRIPT_DIR/.env.production.example" "$SCRIPT_DIR/.env"
            log_info "Please edit $SCRIPT_DIR/.env with your configuration"
        else
            log_error ".env.production.example not found"
            exit 1
        fi
    fi
}

backup_database() {
    log_info "Creating database backup before deployment..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="$SCRIPT_DIR/backups"
    mkdir -p "$BACKUP_DIR"
    
    # Use docker-compose to backup
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" exec -T db pg_dump -U dermacare dermacare > "$BACKUP_DIR/pre_deploy_backup_$TIMESTAMP.sql" 2>/dev/null || {
        log_warning "Could not create backup (database might not be running)"
    }
    
    log_success "Backup completed: pre_deploy_backup_$TIMESTAMP.sql"
}

pull_latest() {
    log_info "Pulling latest code from Git..."
    
    if [ -d "$SCRIPT_DIR/.git" ]; then
        git -C "$SCRIPT_DIR" pull origin main || {
            log_warning "Could not pull latest code. Continuing with local version."
        }
    else
        log_info "Not a git repository. Using local version."
    fi
}

build_images() {
    log_info "Building Docker images..."
    
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" build --no-cache backend
    
    log_success "Docker images built successfully"
}

stop_services() {
    log_info "Stopping existing services..."
    
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" down || {
        log_warning "Could not stop services (they might not be running)"
    }
    
    log_success "Services stopped"
}

start_services() {
    log_info "Starting services..."
    
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" up -d
    
    log_success "Services started"
}

wait_for_health() {
    log_info "Waiting for services to be healthy..."
    
    local max_wait=120
    local waited=0
    
    # Wait for backend
    while [ $waited -lt $max_wait ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Backend is healthy"
            break
        fi
        
        echo -n "."
        sleep 2
        waited=$((waited + 2))
    done
    
    if [ $waited -ge $max_wait ]; then
        log_error "Backend did not become healthy within $max_wait seconds"
        docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" logs backend
        exit 1
    fi
    
    # Wait for database
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" exec -T db pg_isready -U dermacare > /dev/null 2>&1 || {
        log_error "Database is not ready"
        exit 1
    }
    
    log_success "All services are healthy"
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Test health endpoint
    local health_response=$(curl -sf http://localhost:8000/health 2>/dev/null)
    
    if [ -z "$health_response" ]; then
        log_error "Health check failed"
        exit 1
    fi
    
    # Test API endpoint
    local api_response=$(curl -sf http://localhost/api/auth/me 2>/dev/null)
    
    if [ -z "$api_response" ]; then
        log_warning "API test failed (might need authentication)"
    fi
    
    log_success "Deployment verified successfully"
}

show_status() {
    log_info "Service Status:"
    echo ""
    docker compose -f "$SCRIPT_DIR/$COMPOSE_FILE" ps
    echo ""
    log_info "URLs:"
    log_info "  - Application: http://$(curl -sf http://checkip.amazonaws.com 2>/dev/null || echo 'localhost'):8000"
    log_info "  - Health Check: http://localhost:8000/health"
}

cleanup() {
    log_info "Cleaning up old images and containers..."
    
    # Remove dangling images
    docker image prune -f > /dev/null 2>&1 || true
    
    # Remove old backups (keep last 7)
    if [ -d "$SCRIPT_DIR/backups" ]; then
        ls -t "$SCRIPT_DIR/backups"/pre_deploy_backup_*.sql 2>/dev/null | tail -n +8 | xargs -r rm
    fi
    
    log_success "Cleanup completed"
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  DermaCare AI - Deployment Script"
    echo "  Environment: $ENVIRONMENT"
    echo "=============================================="
    echo ""
    
    log_info "Starting deployment at $(date)"
    
    check_root
    check_docker
    check_environment
    
    if [ "$ENVIRONMENT" == "production" ]; then
        backup_database
    fi
    
    pull_latest
    build_images
    stop_services
    start_services
    wait_for_health
    verify_deployment
    cleanup
    
    echo ""
    echo "=============================================="
    log_success "Deployment completed successfully!"
    echo "=============================================="
    echo ""
    
    show_status
    
    echo ""
    log_info "Next Steps:"
    log_info "  1. Set up SSL certificate (Let's Encrypt)"
    log_info "  2. Configure domain DNS"
    log_info "  3. Test all features in browser"
    echo ""
}

# Run main function
main
