# Windows Desktop Automation - Start Script
# Run: powershell -ExecutionPolicy Bypass -File start.ps1

param(
    [switch]$Vision,      # Start vision monitor
    [switch]$Apps,        # Start app monitor
    [switch]$All,         # Start all monitors
    [switch]$Stop         # Stop all monitors
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Stop) {
    Write-Host "Stopping all monitors..." -ForegroundColor Yellow
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*monitor.py*" -or 
        $_.CommandLine -like "*vision_monitor.py*" -or
        $_.CommandLine -like "*app_monitor.py*"
    } | Stop-Process -Force
    Write-Host "All monitors stopped" -ForegroundColor Green
    exit 0
}

Write-Host "=== Starting Monitors ===" -ForegroundColor Cyan

# Always start UIA monitor
Write-Host "Starting UIA monitor..." -ForegroundColor Yellow
Start-Process python -ArgumentList "$scriptPath\monitor.py" -WindowStyle Hidden
Write-Host "  monitor.py started" -ForegroundColor Green

if ($Vision -or $All) {
    Write-Host "Starting Vision monitor..." -ForegroundColor Yellow
    Start-Process python -ArgumentList "$scriptPath\vision_monitor.py","--interval","0.5" -WindowStyle Hidden
    Write-Host "  vision_monitor.py started" -ForegroundColor Green
}

if ($Apps -or $All) {
    Write-Host "Starting App monitor..." -ForegroundColor Yellow
    Start-Process python -ArgumentList "$scriptPath\app_monitor.py","--daemon" -WindowStyle Hidden
    Write-Host "  app_monitor.py started" -ForegroundColor Green
}

Write-Host "`nMonitors running. Output files:" -ForegroundColor Cyan
Write-Host "  output/latest.json         - UIA data"
Write-Host "  output/latest.png          - Screenshot"
if ($Vision -or $All) {
    Write-Host "  output/latest_vision.json  - Vision data"
    Write-Host "  output/latest_vision.png   - Annotated screenshot"
}
if ($Apps -or $All) {
    Write-Host "  output/apps.json           - Running apps"
}

Write-Host "`nUsage:" -ForegroundColor Gray
Write-Host "  .\start.ps1          # UIA only"
Write-Host "  .\start.ps1 -Vision  # UIA + Vision"
Write-Host "  .\start.ps1 -All     # All monitors"
Write-Host "  .\start.ps1 -Stop    # Stop all"
