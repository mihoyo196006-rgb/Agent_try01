param(
    [ValidateSet("main", "supplement", "manual")]
    [string]$CaptureKind = "manual",
    [string]$TargetDate = "",
    [string]$PythonPath = "C:\Users\HH\.local\bin\python.cmd",
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("local-snapshot-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $LogFile -Append
}

$argsList = @("read_dayflow_state.py", "--capture-kind", $CaptureKind, "--write")
if ($TargetDate.Trim()) {
    $argsList += @("--target-date", $TargetDate.Trim())
}

Write-Log "Starting Dayflow snapshot: captureKind=$CaptureKind targetDate=$TargetDate"
$pythonOutput = & $PythonPath @argsList 2>&1
$pythonExit = $LASTEXITCODE
$pythonOutput | Tee-Object -FilePath $LogFile -Append
if ($pythonExit -ne 0) {
    Write-Log "Dayflow read reported an error snapshot. Continuing so the cloud message can explain stale or missing data."
}

git add -- data/dayflow/*.json data/phd/mainline.json
git diff --cached --quiet
$hasStagedChanges = ($LASTEXITCODE -ne 0)
if (-not $hasStagedChanges) {
    Write-Log "No snapshot changes to commit."
    exit 0
}

if ($SkipPush) {
    git reset -- data/dayflow/*.json data/phd/mainline.json
    Write-Log "SkipPush set; verified snapshot changes without committing or pushing."
    exit 0
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Update Dayflow snapshot ($CaptureKind $timestamp)"
Write-Log "Committed Dayflow snapshot."

git push origin main
Write-Log "Pushed Dayflow snapshot to origin/main."
