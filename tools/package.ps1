# Builds dist/GorillaAkimbo-<version>.zip for Nexus (game-folder layout: r6/...).
param([string]$Version = "2.1.1")
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force $dist | Out-Null
$zip = Join-Path $dist "GorillaAkimbo-$Version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "archive"), (Join-Path $root "r6") -DestinationPath $zip
"Built $zip"
