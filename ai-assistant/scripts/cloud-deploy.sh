#!/bin/bash
#
# Cloud Deployment Helper Script for AI Assistant
# This script helps deploy and manage the AI Assistant on Google Cloud Platform
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEFAULT_PROJECT_ID="gen-lang-client-0859968110"
DEFAULT_SERVICE_ACCOUNT="connectx@${DEFAULT_PROJECT_ID}.iam.gserviceaccount.com"
DEFAULT_REGION="europe-west3"
DEFAULT_ZONE="europe-west3-a"
IMAGE_NAME="ai-assistant"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Helper functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if required tools are installed
check_requirements() {
    print_header "Checking Requirements"
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        echo "Visit: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    print_success "gcloud CLI found"
    
    if ! command -v podman &> /dev/null && ! command -v docker &> /dev/null; then
        print_error "Neither podman nor docker is installed. Please install one."
        exit 1
    fi
    
    if command -v podman &> /dev/null; then
        CONTAINER_TOOL="podman"
        print_success "Using podman"
    else
        CONTAINER_TOOL="docker"
        print_success "Using docker"
    fi
    
    echo ""
}

# Get project configuration
get_config() {
    PROJECT_ID="${GCP_PROJECT_ID:-$DEFAULT_PROJECT_ID}"
    SERVICE_ACCOUNT="${GCP_SERVICE_ACCOUNT:-$DEFAULT_SERVICE_ACCOUNT}"
    REGION="${GCP_REGION:-$DEFAULT_REGION}"
    ZONE="${GCP_ZONE:-$DEFAULT_ZONE}"
    IMAGE_TAG="gcr.io/${PROJECT_ID}/${IMAGE_NAME}"
}

# Build the container image
build_image() {
    print_header "Building Container Image"
    
    cd "$PROJECT_ROOT"
    
    print_info "Building for AMD64 architecture (Cloud-compatible)..."
    if [ "$CONTAINER_TOOL" = "podman" ]; then
        podman build --platform linux/amd64 -t "$IMAGE_TAG" -f Containerfile .
    else
        docker buildx build --platform linux/amd64 -t "$IMAGE_TAG" -f Containerfile .
    fi
    
    print_success "Image built successfully: $IMAGE_TAG"
    echo ""
}

# Push image to Google Container Registry
push_image() {
    print_header "Pushing Image to GCR"
    
    print_info "Configuring authentication..."
    gcloud auth configure-docker gcr.io --quiet
    
    print_info "Pushing image..."
    $CONTAINER_TOOL push "$IMAGE_TAG"
    
    print_success "Image pushed successfully"
    echo ""
}

# Deploy to Compute Engine (recommended for WebRTC)
deploy_compute_engine() {
    print_header "Deploying to Compute Engine"
    
    VM_NAME="${1:-ai-assistant-vm}"
    MACHINE_TYPE="${2:-e2-medium}"
    
    print_info "VM Name: $VM_NAME"
    print_info "Machine Type: $MACHINE_TYPE"
    print_info "Zone: $ZONE"
    
    # Check if VM already exists
    if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" &> /dev/null; then
        print_warning "VM '$VM_NAME' already exists."
        read -p "Do you want to delete and recreate it? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Deleting existing VM..."
            gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet
        else
            print_info "Updating existing VM..."
            gcloud compute instances update-container "$VM_NAME" \
                --zone="$ZONE" \
                --container-image="$IMAGE_TAG" \
                --container-env="GEMINI_API_KEY=${GEMINI_API_KEY},LANGUAGE_CODE=${LANGUAGE_CODE:-de-DE},VOICE_NAME=${VOICE_NAME:-de-DE-Chirp-HD-F},LOG_LEVEL=${LOG_LEVEL:-INFO}"
            print_success "VM updated successfully"
            return
        fi
    fi
    
    # Create VM
    print_info "Creating VM with container..."
    gcloud compute instances create-with-container "$VM_NAME" \
        --container-image="$IMAGE_TAG" \
        --container-env="GEMINI_API_KEY=${GEMINI_API_KEY},LANGUAGE_CODE=${LANGUAGE_CODE:-de-DE},VOICE_NAME=${VOICE_NAME:-de-DE-Chirp-HD-F},LOG_LEVEL=${LOG_LEVEL:-INFO}" \
        --machine-type="$MACHINE_TYPE" \
        --zone="$ZONE" \
        --tags=ai-assistant \
        --service-account="$SERVICE_ACCOUNT" \
        --scopes=cloud-platform
    
    # Create firewall rule if it doesn't exist
    if ! gcloud compute firewall-rules describe allow-ai-assistant &> /dev/null; then
        print_info "Creating firewall rule..."
        gcloud compute firewall-rules create allow-ai-assistant \
            --allow tcp:8080,udp:49152-65535 \
            --target-tags=ai-assistant \
            --source-ranges=0.0.0.0/0 \
            --description="Allow WebSocket and WebRTC traffic for AI Assistant"
    fi
    
    print_success "VM created successfully"
    
    # Get external IP
    sleep 5
    EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    print_success "Deployment complete!"
    echo ""
    print_info "External IP: $EXTERNAL_IP"
    print_info "Health endpoint: http://$EXTERNAL_IP:8080/health"
    print_info "WebSocket endpoint: ws://$EXTERNAL_IP:8080/ws"
    echo ""
    print_warning "Note: It may take 1-2 minutes for the container to start."
    echo ""
}

# Deploy to Cloud Run (limited - no WebRTC UDP support)
deploy_cloud_run() {
    print_header "Deploying to Cloud Run"
    
    SERVICE_NAME="${1:-ai-assistant}"
    
    print_warning "Note: Cloud Run does not support WebRTC UDP traffic."
    print_warning "This deployment is for testing HTTP/WebSocket only."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled"
        return
    fi
    
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --platform managed \
        --region "$REGION" \
        --port 8080 \
        --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},LANGUAGE_CODE=${LANGUAGE_CODE:-de-DE},VOICE_NAME=${VOICE_NAME:-de-DE-Chirp-HD-F},LOG_LEVEL=${LOG_LEVEL:-INFO}" \
        --service-account "$SERVICE_ACCOUNT" \
        --allow-unauthenticated \
        --min-instances 0 \
        --max-instances 10 \
        --memory 1Gi \
        --timeout 300
    
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')
    
    print_success "Deployment complete!"
    echo ""
    print_info "Service URL: $SERVICE_URL"
    print_info "Health endpoint: $SERVICE_URL/health"
    print_info "WebSocket endpoint: ${SERVICE_URL/https/wss}/ws"
    echo ""
}

# Stop VM
stop_vm() {
    VM_NAME="${1:-ai-assistant-vm}"
    
    print_header "Stopping VM"
    print_info "VM: $VM_NAME"
    
    gcloud compute instances stop "$VM_NAME" --zone="$ZONE"
    
    print_success "VM stopped successfully"
    echo ""
}

# Start VM
start_vm() {
    VM_NAME="${1:-ai-assistant-vm}"
    
    print_header "Starting VM"
    print_info "VM: $VM_NAME"
    
    gcloud compute instances start "$VM_NAME" --zone="$ZONE"
    
    sleep 5
    EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    print_success "VM started successfully"
    print_info "External IP: $EXTERNAL_IP"
    print_info "Health endpoint: http://$EXTERNAL_IP:8080/health"
    echo ""
}

# Delete VM
delete_vm() {
    VM_NAME="${1:-ai-assistant-vm}"
    
    print_header "Deleting VM"
    print_warning "This will permanently delete the VM: $VM_NAME"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deletion cancelled"
        return
    fi
    
    gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet
    
    print_success "VM deleted successfully"
    echo ""
}

# Get VM status
status_vm() {
    VM_NAME="${1:-ai-assistant-vm}"
    
    print_header "VM Status"
    
    if ! gcloud compute instances describe "$VM_NAME" --zone="$ZONE" &> /dev/null; then
        print_error "VM '$VM_NAME' does not exist"
        return
    fi
    
    STATUS=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format='get(status)')
    EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    echo "VM Name: $VM_NAME"
    echo "Status: $STATUS"
    echo "Zone: $ZONE"
    echo "External IP: $EXTERNAL_IP"
    
    if [ "$STATUS" = "RUNNING" ]; then
        echo ""
        print_info "Testing health endpoint..."
        if curl -s -f "http://$EXTERNAL_IP:8080/health" > /dev/null 2>&1; then
            print_success "Service is healthy"
            curl -s "http://$EXTERNAL_IP:8080/health"
        else
            print_warning "Service not responding (container may still be starting)"
        fi
    fi
    echo ""
}

# View logs
logs_vm() {
    VM_NAME="${1:-ai-assistant-vm}"
    
    print_header "VM Logs"
    print_info "Fetching serial console output..."
    echo ""
    
    gcloud compute instances get-serial-port-output "$VM_NAME" --zone="$ZONE" | tail -100
}

# Show usage
usage() {
    cat << EOF
${BLUE}AI Assistant Cloud Deployment Helper${NC}

${GREEN}Usage:${NC}
    $0 <command> [options]

${GREEN}Commands:${NC}
    ${YELLOW}build${NC}                  Build the container image (AMD64 architecture)
    ${YELLOW}push${NC}                   Push the image to Google Container Registry
    ${YELLOW}deploy${NC}                 Full deployment (build + push + deploy to Compute Engine)
    ${YELLOW}deploy-ce [vm-name]${NC}    Deploy to Compute Engine (recommended for WebRTC)
    ${YELLOW}deploy-run [service]${NC}   Deploy to Cloud Run (limited - no WebRTC UDP)
    ${YELLOW}start [vm-name]${NC}        Start a stopped VM
    ${YELLOW}stop [vm-name]${NC}         Stop a running VM
    ${YELLOW}delete [vm-name]${NC}       Delete a VM
    ${YELLOW}status [vm-name]${NC}       Show VM status and test health endpoint
    ${YELLOW}logs [vm-name]${NC}         View VM logs
    ${YELLOW}config${NC}                 Show current configuration

${GREEN}Environment Variables:${NC}
    GCP_PROJECT_ID          Google Cloud project ID (default: $DEFAULT_PROJECT_ID)
    GCP_SERVICE_ACCOUNT     Service account email (default: $DEFAULT_SERVICE_ACCOUNT)
    GCP_REGION              Region for Cloud Run (default: $DEFAULT_REGION)
    GCP_ZONE                Zone for Compute Engine (default: $DEFAULT_ZONE)
    GEMINI_API_KEY          Gemini API key (required)
    LANGUAGE_CODE           Language code (default: de-DE)
    VOICE_NAME              Voice name (default: de-DE-Chirp-HD-F)
    LOG_LEVEL               Logging level (default: INFO)

${GREEN}Examples:${NC}
    # Full deployment to Compute Engine
    $0 deploy

    # Deploy with custom VM name and machine type
    $0 deploy-ce my-ai-assistant e2-standard-2

    # Check status
    $0 status

    # Stop VM to save costs
    $0 stop

    # Start VM again
    $0 start

    # View logs
    $0 logs

${GREEN}Notes:${NC}
    - Compute Engine is recommended for WebRTC (requires UDP support)
    - Cloud Run is cheaper but doesn't support WebRTC UDP traffic
    - Default VM is e2-medium (~\$24/month when running)
    - Stop VM when not in use to save costs

EOF
}

# Show configuration
show_config() {
    print_header "Current Configuration"
    echo "Project ID: $PROJECT_ID"
    echo "Service Account: $SERVICE_ACCOUNT"
    echo "Region: $REGION"
    echo "Zone: $ZONE"
    echo "Image Tag: $IMAGE_TAG"
    echo "Container Tool: $CONTAINER_TOOL"
    echo ""
    echo "Environment:"
    echo "  GEMINI_API_KEY: ${GEMINI_API_KEY:+****${GEMINI_API_KEY: -4}}"
    echo "  LANGUAGE_CODE: ${LANGUAGE_CODE:-de-DE}"
    echo "  VOICE_NAME: ${VOICE_NAME:-de-DE-Chirp-HD-F}"
    echo "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"
    echo ""
}

# Main script
main() {
    check_requirements
    get_config
    
    COMMAND="${1:-help}"
    shift || true
    
    case "$COMMAND" in
        build)
            build_image
            ;;
        push)
            push_image
            ;;
        deploy)
            build_image
            push_image
            deploy_compute_engine "$@"
            ;;
        deploy-ce)
            deploy_compute_engine "$@"
            ;;
        deploy-run)
            deploy_cloud_run "$@"
            ;;
        start)
            start_vm "$@"
            ;;
        stop)
            stop_vm "$@"
            ;;
        delete)
            delete_vm "$@"
            ;;
        status)
            status_vm "$@"
            ;;
        logs)
            logs_vm "$@"
            ;;
        config)
            show_config
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo ""
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
