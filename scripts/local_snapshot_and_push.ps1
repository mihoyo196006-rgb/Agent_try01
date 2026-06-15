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

$argsList = @("read_dayflow_state.py", "--capture-kind", $CaptureKind, "--write")
if ($TargetDate.Trim()) {
    $argsList += @("--target-date", $TargetDate.Trim())
}

& $PythonPath @argsList
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Dayflow read reported an error snapshot. Continuing so the cloud message can explain stale or missing data."
}

git add -- data/dayflow/*.json data/phd/mainline.json
$hasStagedChanges = git diff --cached --quiet; $LASTEXITCODE -ne 0
if (-not $hasStagedChanges) {
    Write-Host "No snapshot changes to commit."
    exit 0
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Update Dayflow snapshot ($CaptureKind $timestamp)"

if ($SkipPush) {
    Write-Host "SkipPush set; leaving commit local."
    exit 0
}

git push origin main
