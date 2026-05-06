# Market_Sentry - Generic Scheduled Task Wrapper
# Reusable PowerShell wrapper for scheduled Market_Sentry commands.
# All commands run local workflows only. No live scraping or network calls.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("watchlist-refresh", "initial-review", "dashboard-summary", "fixture-demo")]
    [string]$CommandName,

    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "",

    [Parameter(Mandatory=$false)]
    [string]$DatabasePath = "",

    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "",

    [Parameter(Mandatory=$false)]
    [string]$LogDir = ""
)

# Determine project root
if ($ProjectRoot -eq "") {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
}

# Change to project root
Set-Location -Path $ProjectRoot

# Set up log directory
if ($LogDir -eq "") {
    $LogDir = Join-Path $ProjectRoot "logs\scheduled"
}
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Create timestamped log file
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SafeCommandName = $CommandName -replace "-", "_"
$LogFile = Join-Path $LogDir "${SafeCommandName}_${Timestamp}.log"

# Map command name to CLI command
$CliCommandMap = @{
    "watchlist-refresh" = "run-watchlist-refresh-workflow"
    "initial-review"    = "run-initial-review-workflow"
    "dashboard-summary" = "dashboard-summary"
    "fixture-demo"      = "run-fixture-demo-workflow"
}
$CliCommand = $CliCommandMap[$CommandName]

# Start logging
$StartTime = Get-Date
"==================================================" | Out-File -FilePath $LogFile -Encoding utf8
"Market_Sentry Scheduled Task: $CommandName" | Out-File -FilePath $LogFile -Append -Encoding utf8
"Start: $($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))" | Out-File -FilePath $LogFile -Append -Encoding utf8
"Working Directory: $ProjectRoot" | Out-File -FilePath $LogFile -Append -Encoding utf8
"==================================================" | Out-File -FilePath $LogFile -Append -Encoding utf8

# Detect and activate virtual environment
$VenvActivated = $false
$VenvPython = $null

if (Test-Path (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) {
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    "Using virtualenv: .venv" | Out-File -FilePath $LogFile -Append -Encoding utf8
    $VenvActivated = $true
} elseif (Test-Path (Join-Path $ProjectRoot "venv\Scripts\python.exe")) {
    $VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    "Using virtualenv: venv" | Out-File -FilePath $LogFile -Append -Encoding utf8
    $VenvActivated = $true
} else {
    "No virtual environment found, using system Python" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# Determine Python executable
if ($VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = "python"
}

# Log Python version
"Python executable: $PythonExe" | Out-File -FilePath $LogFile -Append -Encoding utf8
& $PythonExe --version 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8

# Build CLI arguments
$CliArgs = @("-c", "from marketsentry.cli import app; app()", $CliCommand)

if ($DatabasePath -ne "") {
    $CliArgs += "--db"
    $CliArgs += $DatabasePath
}

if ($OutputDir -ne "" -and $CommandName -ne "dashboard-summary") {
    $CliArgs += "--output-dir"
    $CliArgs += $OutputDir
}

if ($CommandName -eq "fixture-demo") {
    $CliArgs += "--reset-demo-db"
}

# Log the command
"" | Out-File -FilePath $LogFile -Append -Encoding utf8
"Running: $PythonExe $($CliArgs -join ' ')" | Out-File -FilePath $LogFile -Append -Encoding utf8
"==================================================" | Out-File -FilePath $LogFile -Append -Encoding utf8

# Execute the command
try {
    & $PythonExe $CliArgs 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) { $ExitCode = 0 }
} catch {
    "ERROR: $($_.Exception.Message)" | Out-File -FilePath $LogFile -Append -Encoding utf8
    $ExitCode = 1
}

# End logging
$EndTime = Get-Date
$Duration = ($EndTime - $StartTime).TotalSeconds
"==================================================" | Out-File -FilePath $LogFile -Append -Encoding utf8
"Exit Code: $ExitCode" | Out-File -FilePath $LogFile -Append -Encoding utf8
"Duration: $([math]::Round($Duration, 1))s" | Out-File -FilePath $LogFile -Append -Encoding utf8
"End: $($EndTime.ToString('yyyy-MM-dd HH:mm:ss'))" | Out-File -FilePath $LogFile -Append -Encoding utf8
"==================================================" | Out-File -FilePath $LogFile -Append -Encoding utf8

Write-Host "Log written to: $LogFile"

exit $ExitCode
