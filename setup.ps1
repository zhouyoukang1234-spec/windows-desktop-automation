# Windows Desktop Automation - Quick Setup Script
# Run: powershell -ExecutionPolicy Bypass -File setup.ps1

Write-Host "=== Windows Desktop Automation Setup ===" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Please install Python 3.8+" -ForegroundColor Red
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

$version = python --version
Write-Host "Python: $version" -ForegroundColor Green

# Create virtual environment (optional)
$useVenv = Read-Host "Create virtual environment? (y/n, default: n)"
if ($useVenv -eq 'y') {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    Write-Host "Virtual environment activated" -ForegroundColor Green
}

# Install dependencies
Write-Host "`nInstalling core dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Check CUDA for GPU acceleration (optional)
Write-Host "`nChecking GPU support..." -ForegroundColor Yellow
$cuda = python -c "import torch; print(torch.cuda.is_available())" 2>$null
if ($cuda -eq 'True') {
    Write-Host "CUDA available - GPU acceleration enabled" -ForegroundColor Green
} else {
    Write-Host "CUDA not available - using CPU mode" -ForegroundColor Yellow
    Write-Host "For GPU: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118" -ForegroundColor Gray
}

# Create output directory
if (-not (Test-Path "output")) {
    New-Item -ItemType Directory -Path "output" | Out-Null
    Write-Host "Created output directory" -ForegroundColor Green
}

# Test imports
Write-Host "`nTesting imports..." -ForegroundColor Yellow
$test = python -c "
import pyautogui
import pyperclip
import mss
import cv2
import numpy
import win32gui
print('All core imports OK')
" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $test -ForegroundColor Green
} else {
    Write-Host "Import test failed: $test" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host @"

Quick Start:
  # Start monitoring system
  Start-Process python -ArgumentList "monitor.py" -WindowStyle Hidden
  Start-Process python -ArgumentList "vision_monitor.py","--interval","0.5" -WindowStyle Hidden
  Start-Process python -ArgumentList "app_monitor.py","--daemon" -WindowStyle Hidden

  # Or use the start script
  .\start.ps1

Documentation:
  - README.md           - Project overview
  - OPERATION_MANUAL.md - Full operation guide
  - RESEARCH_SUMMARY.md - Multi-monitor solution

"@ -ForegroundColor White
