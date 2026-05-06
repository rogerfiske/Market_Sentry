# Market_Sentry - Uninstall Windows Task Scheduler for Watchlist Refresh
# Removes the scheduled task created by install_task_scheduler_watchlist_refresh.ps1.
#
# Usage:
#   .\uninstall_task_scheduler_watchlist_refresh.ps1
#   .\uninstall_task_scheduler_watchlist_refresh.ps1 -TaskName "Custom_Task_Name"

param(
    [Parameter(Mandatory=$false)]
    [string]$TaskName = "Market_Sentry_Watchlist_Refresh"
)

Write-Host "=============================================="
Write-Host "Market_Sentry Task Scheduler Uninstall"
Write-Host "=============================================="

# Check if task exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $ExistingTask) {
    Write-Host "Task '$TaskName' not found. Nothing to remove." -ForegroundColor Yellow
    exit 0
}

# Remove the task
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

    Write-Host ""
    Write-Host "SUCCESS: Scheduled task '$TaskName' has been removed." -ForegroundColor Green
    Write-Host ""
    Write-Host "Scheduled log files in logs\scheduled\ are preserved."
    Write-Host "To reinstall: .\install_task_scheduler_watchlist_refresh.ps1"
} catch {
    Write-Host "ERROR: Failed to remove scheduled task." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
