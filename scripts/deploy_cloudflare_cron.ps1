param(
  [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..\cloudflare").Path
)

$ErrorActionPreference = "Stop"

if (-not $env:CLOUDFLARE_API_TOKEN) {
  throw "CLOUDFLARE_API_TOKEN is required in the environment."
}

$larkConfigPath = Join-Path $HOME ".lark-cli\config.json"
if (-not (Test-Path -LiteralPath $larkConfigPath)) {
  throw "Missing lark-cli config: $larkConfigPath"
}

$larkConfig = Get-Content -Raw -LiteralPath $larkConfigPath | ConvertFrom-Json
$app = @($larkConfig.apps | Where-Object { $_.appId -eq "cli_aaa0102e6a38dcff" })[0]
if (-not $app -or -not $app.appSecret) {
  throw "Missing Feishu app secret in lark-cli config."
}

$dayflowSecretPath = Join-Path $env:LOCALAPPDATA "DayflowCloudSync\secrets.json"
if (-not (Test-Path -LiteralPath $dayflowSecretPath)) {
  throw "Missing DayFlow cloud secrets: $dayflowSecretPath"
}

$dayflowSecrets = Get-Content -Raw -LiteralPath $dayflowSecretPath | ConvertFrom-Json
$required = @{
  FEISHU_APP_SECRET = $app.appSecret
  DAYFLOW_WRITE_TOKEN = $dayflowSecrets.dayflowWriteToken
  DAYFLOW_READ_TOKEN = $dayflowSecrets.dayflowReadToken
}

Push-Location $ProjectDir
try {
  foreach ($entry in $required.GetEnumerator()) {
    if (-not $entry.Value) {
      throw "Missing value for $($entry.Key)."
    }
    $entry.Value | & D:\Nodejs\npx.cmd wrangler secret put $entry.Key
  }

  & D:\Nodejs\npx.cmd wrangler deploy
} finally {
  Pop-Location
}
