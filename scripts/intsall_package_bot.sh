#!/bin/bash
# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Define logging functions
log_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

log_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1" >&2
}

# Check for available Python command
log_info "Detecting available Python command..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    log_info "Found python3 command"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    log_info "Found python command"
else
    log_error "No Python interpreter found. Please install Python 3."
    exit 1
fi

# Determine pip command
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    log_info "Found pip3 command"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    log_info "Found pip command"
else
    log_error "No pip command found. Please install pip."
    exit 1
fi

# Install required packages if pip is available
if [ -n "$PIP_CMD" ]; then
    log_info "Installing required packages using $PIP_CMD..."
    if ! $PIP_CMD install -r requirements.txt --user; then
        log_error "Failed to install required packages"
        exit 1
    fi
else
    log_info "Skipping package installation since pip is not available."
fi
