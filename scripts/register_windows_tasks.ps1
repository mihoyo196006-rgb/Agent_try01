param(
    [string]$PythonPath = "C:\Users\HH\.local\bin\python.cmd"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SnapshotScript = Join-Path $RepoRoot "scripts\local_snapshot_and_push.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

function Register-DayflowTask {
    param(
        [string]$Name,
        [string]$Time,
        [string]$CaptureKind
    )

    $argument = "-NoProfile -ExecutionPolicy Bypass -File `"$SnapshotScript`" -CaptureKind $CaptureKind -PythonPath `"$PythonPath`""
    $action = New-ScheduledTaskAction -Execute $PowerShell -Argument $argument -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Description "Dayflow Feishu daily snapshot ($CaptureKind)" -Force | Out-Null
    Write-Host "Registered $Name at $Time"
}

Register-DayflowTask -Name "DayflowFeishuSnapshot2350" -Time "23:50" -CaptureKind "main"
Register-DayflowTask -Name "DayflowFeishuSnapshot0010" -Time "00:10" -CaptureKind "supplement"
