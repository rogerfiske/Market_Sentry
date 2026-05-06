# Market_Sentry - Install Windows Task Scheduler for Watchlist Refresh
# Creates a scheduled task that runs the watchlist refresh workflow weekly.
# The task runs local workflows only. No live scraping or network calls.
#
# Usage:
#   .\install_task_scheduler_watchlist_refresh.ps1
#   .\install_task_scheduler_watchlist_refresh.ps1 -DayOfWeek "Monday" -Time "08:00"
#   .\install_task_scheduler_watchlist_refresh.ps1 -ProjectRoot "C:\path\to\Market_Sentry"

param(
    [Parameter(Mandatory=$false)]
    [string]$TaskName = "Market_Sentry_Watchlist_Refresh",

    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "",

    [Parameter(Mandatory=$false)]
    [ValidateSet("Weekly", "Daily")]
    [string]$Schedule = "Weekly",

    [Parameter(Mandatory=$false)]
    [ValidateSet("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")]
    [string]$DayOfWeek = "Saturday",

    [Parameter(Mandatory=$false)]
    [string]$Time = "09:00",

    [Parameter(Mandatory=$false)]
    [string]$PythonExe = "",

    [Parameter(Mandatory=$false)]
    [string]$DatabasePath = "",

    [Parameter(Mandatory=$false)]
    [string]$OutputDir = ""
)

Write-Host "=============================================="
Write-Host "Market_Sentry Task Scheduler Install"
Write-Host "=============================================="

# Determine project root
if ($ProjectRoot -eq "") {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
}
Write-Host "Project Root: $ProjectRoot"

# Verify project root exists
if (-not (Test-Path $ProjectRoot)) {
    Write-Host "ERROR: Project root not found: $ProjectRoot" -ForegroundColor Red
    exit 1
}

# Verify the wrapper script exists
$WrapperScript = Join-Path $ProjectRoot "scripts\run_marketsentry_task.ps1"
if (-not (Test-Path $WrapperScript)) {
    Write-Host "ERROR: Wrapper script not found: $WrapperScript" -ForegroundColor Red
    exit 1
}

# Build the action arguments
$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$WrapperScript`" -CommandName watchlist-refresh -ProjectRoot `"$ProjectRoot`""

if ($DatabasePath -ne "") {
    $ActionArgs += " -DatabasePath `"$DatabasePath`""
}
if ($OutputDir -ne "") {
    $ActionArgs += " -OutputDir `"$OutputDir`""
}

# Determine PowerShell executable
$PwshExe = "powershell.exe"
if (Get-Command "pwsh.exe" -ErrorAction SilentlyContinue) {
    $PwshExe = "pwsh.exe"
}

# Create the scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute $PwshExe `
    -Argument $ActionArgs `
    -WorkingDirectory $ProjectRoot

# Create the trigger
if ($Schedule -eq "Weekly") {
    $Trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek $DayOfWeek `
        -At $Time
} else {
    $Trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At $Time
}

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# Description
$Description = "Market_Sentry watchlist refresh workflow. Runs local data processing only (SQLite, CSV, HTML fixtures). No live scraping or network calls."

# Check if task already exists and remove it
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Existing task '$TaskName' found. Replacing..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register the task (runs only when user is logged on)
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description $Description `
        -RunLevel Limited

    Write-Host ""
    Write-Host "SUCCESS: Scheduled task created." -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:"
    Write-Host "  Name:      $TaskName"
    Write-Host "  Schedule:  $Schedule"
    if ($Schedule -eq "Weekly") {
        Write-Host "  Day:       $DayOfWeek"
    }
    Write-Host "  Time:      $Time"
    Write-Host "  Command:   watchlist-refresh"
    Write-Host "  Logs:      $ProjectRoot\logs\scheduled\"
    Write-Host ""
    Write-Host "To verify:  Get-ScheduledTask -TaskName '$TaskName'"
    Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "To remove:  .\uninstall_task_scheduler_watchlist_refresh.ps1"
    Write-Host ""
    Write-Host "NOTE: This task runs LOCAL workflows only."
    Write-Host "No live scraping or network calls are performed."
} catch {
    Write-Host "ERROR: Failed to create scheduled task." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
