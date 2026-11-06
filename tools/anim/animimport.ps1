# Imports animations from a glb into an existing .anims file (in place), via WolvenKit's library.
# Usage: pwsh animimport.ps1 <glb> <anims>
# WK_DIR: the WolvenKit CLI folder. GAME: the Cyberpunk 2077 folder (the rig is read from its archives).
param([string]$Glb, [string]$Anims)
$d = if ($env:WK_DIR) { $env:WK_DIR } else { 'C:\Modding\_tools\wolvenkit-cli' }
$game = if ($env:GAME) { $env:GAME } else { 'C:\Program Files (x86)\Steam\steamapps\common\Cyberpunk 2077' }
$env:WK_DIR = $d
[AppContext]::SetData('APP_CONTEXT_BASE_DIRECTORY', "$d\")
[AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e)
    $n = (New-Object Reflection.AssemblyName $e.Name).Name
    $p = "$env:WK_DIR\$n.dll"
    if (Test-Path $p) { [Reflection.Assembly]::LoadFrom($p) } else { $null } })
Push-Location $d
$cli = [Reflection.Assembly]::LoadFrom("$d\WolvenKit.CLI.dll")
$mk = [Reflection.Assembly]::LoadFrom("$d\WolvenKit.Modkit.dll")
$common = [Reflection.Assembly]::LoadFrom("$d\WolvenKit.Common.dll")
$host_ = $cli.GetType('WolvenKit.CLI.GenericHost').GetMethod('CreateHostBuilder').Invoke($null, @(, [string[]]@())).Build()
$mt = $mk.GetType('WolvenKit.Modkit.RED4.ModTools')
$tools = $host_.Services.GetService($mt)
if (-not $tools) {
    foreach ($i in $mt.GetInterfaces()) { $tools = $host_.Services.GetService($i); if ($tools) { break } }
}
if (-not $tools) {
    $tools = [Microsoft.Extensions.DependencyInjection.ActivatorUtilities]::CreateInstance($host_.Services, $mt, [object[]]@())
}
if (-not $tools) { throw 'ModTools not resolved' }
$argsT = $common.GetType('WolvenKit.Common.Model.Arguments.GltfImportArgs')
$ia = [Activator]::CreateInstance($argsT)
$fmtT = $argsT.GetProperty('ImportFormat').PropertyType
$ia.ImportFormat = [Enum]::Parse($fmtT, 'Anims')
$ia.ShowVerboseLogOutput = $true
$amT = $common.GetType('WolvenKit.Common.IArchiveManager')
$am = $host_.Services.GetService($amT)
$exe = [IO.FileInfo]"$game\bin\x64\Cyberpunk2077.exe"
$init = $amT.GetMethods() | Where-Object { $_.Name -eq 'Initialize' -and $_.GetParameters()[0].ParameterType -eq [IO.FileInfo] } | Select-Object -First 1
$p = @($exe) + @($init.GetParameters() | Select-Object -Skip 1 | ForEach-Object { if ($_.HasDefaultValue) { $_.DefaultValue } else { $false } })
[void]$init.Invoke($am, [object[]]$p)
$m = $mt.GetMethods() | Where-Object { $_.Name -eq 'ImportAnims' -and $_.GetParameters()[0].ParameterType.Name -eq 'FileInfo' }
$fs = [IO.File]::Open($Anims, 'Open', 'ReadWrite')
try { $ok = $m.Invoke($tools, @([IO.FileInfo]$Glb, $fs, $ia)) } finally { $fs.Dispose() }
Pop-Location
"import ok: $ok"
