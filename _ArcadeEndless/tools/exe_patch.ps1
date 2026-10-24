<#
Arcade Endless exe patch, for players without Python. Same patch and checks as exe_patch.py:

  powershell -ExecutionPolicy Bypass -File exe_patch.ps1 status | install | remove | restore

Makes world_time_of_day::get_total_game_duration() return 190 instead of the hardcoded 45, so the game
generates pester waves past day 44. 6 bytes change; `remove` writes the original 6 back. The site is found by
pattern and the script refuses to touch an exe it doesn't recognise. Before patching an unpatched exe, `install`
saves a full copy next to it (<exe>.arcade-backup, refreshed after a game update); `restore` copies it back.
#>
param(
    [ValidateSet("status", "install", "remove", "restore")][string]$Command = "status",
    [string]$Exe = ""
)
$ErrorActionPreference = "Stop"
$PatchDays = 190
$VanillaDays = 45
if (-not $Exe) { $Exe = Join-Path $PSScriptRoot "..\..\Achilles\Binaries\Win64\Achilles-Win64-Shipping.exe" }
$Exe = (Resolve-Path $Exe).Path
$Backup = "$Exe.arcade-backup"    # the unpatched exe, saved by install

$Head = [byte[]](0x48, 0x8B, 0x49, 0x10, 0x48, 0x81)        # mov rcx,[rcx+10h]; add rcx,... (replaced)
$Tail = [byte[]](0xC1, 0x00, 0x01, 0x00, 0x00, 0xE9)        # ...100h; jmp rel32 (kept)

function Test-Bytes($bytes, $at, $want) {
    for ($k = 0; $k -lt $want.Length; $k++) { if ($bytes[$at + $k] -ne $want[$k]) { return $false } }
    return $true
}

function Find-Site($bytes) {
    $latin1 = [System.Text.Encoding]::GetEncoding(28591)    # 1 byte = 1 char, so string search finds byte patterns
    $text = $latin1.GetString($bytes)
    $tailText = $latin1.GetString($Tail)
    $found = @()
    $i = $text.IndexOf($tailText, [StringComparison]::Ordinal)
    while ($i -ge 0) {
        $site = $i - 6
        if ($site -ge 0) {
            $t = $site + 16 + [BitConverter]::ToInt32($bytes, $site + 12)   # jmp must land on get_game_duration:
            if ($t -ge 0 -and $t + 11 -le $bytes.Length -and                # cvtss2si eax,[rip+x]; sar eax,1; ret
                (Test-Bytes $bytes $t ([byte[]](0xF3, 0x0F, 0x2D, 0x05))) -and
                (Test-Bytes $bytes ($t + 8) ([byte[]](0xD1, 0xF8, 0xC3)))) {
                if (Test-Bytes $bytes $site $Head) { $found += , @($site, $null) }
                elseif ($bytes[$site] -eq 0xB8 -and $bytes[$site + 5] -eq 0xC3) { $found += , @($site, [BitConverter]::ToUInt32($bytes, $site + 1)) }
            }
        }
        $i = $text.IndexOf($tailText, $i + 1, [StringComparison]::Ordinal)
    }
    if ($found.Count -ne 1) { throw "Patch site found $($found.Count) times in $Exe; this game version isn't supported. Nothing changed." }
    return $found[0]
}

function Write-Head($site, [byte[]]$head) {
    try {
        $f = [System.IO.File]::Open($Exe, "Open", "ReadWrite", "None")
    } catch {
        throw "Can't write the exe. Close the game (and anything holding the file) and run this again."
    }
    try { $f.Seek($site, "Begin") | Out-Null; $f.Write($head, 0, 6) } finally { $f.Close() }
    $check = [System.IO.File]::ReadAllBytes($Exe)
    if (-not (Test-Bytes $check $site $head)) { throw "write did not stick" }
}

function Same-File($a, $b) { (Test-Path $b) -and ((Get-FileHash $a).Hash -eq (Get-FileHash $b).Hash) }

if ($Command -eq "restore") {
    if (-not (Test-Path $Backup)) {
        throw "No backup at $Backup; nothing to restore. Steam's 'Verify integrity of game files' also puts the original exe back."
    }
    $saved, $savedDays = Find-Site ([System.IO.File]::ReadAllBytes($Backup))
    if ($null -ne $savedDays) { throw "$Backup isn't an unpatched game exe; not restoring it." }
    try { Copy-Item $Backup $Exe -Force } catch { throw "Can't write the exe. Close the game (and anything holding the file) and run this again." }
    Write-Output "Restored the original exe from $Backup."
    exit 0
}
$bytes = [System.IO.File]::ReadAllBytes($Exe)
$site, $days = Find-Site $bytes
$state = if ($null -eq $days) { "vanilla ($VanillaDays days of waves)" } else { "patched ($days days of waves)" }
switch ($Command) {
    "status" {
        Write-Output "$Exe`n  $state, patch site at file offset 0x$('{0:x}' -f $site)"
        $modPak = Join-Path (Split-Path $Exe) "..\..\Content\Paks\~mods\ArcadeEndless_P.pak"
        if (Test-Path $modPak) {    # first 8 hex digits of SHA-256: compare with the host's match code
            Write-Output "  ArcadeEndless_P.pak: match code $((Get-FileHash $modPak -Algorithm SHA256).Hash.Substring(0, 8).ToLower())"
        } else { Write-Output "  ArcadeEndless_P.pak: not in ~mods" }
        if (-not (Test-Path $Backup)) { Write-Output "  backup: none yet (install makes one)" }
        elseif (Same-File $Exe $Backup) { Write-Output "  backup: $Backup (same as the exe now)" }
        else { Write-Output "  backup: $Backup" }
    }
    "install" {
        if ($days -eq $PatchDays) { Write-Output "Already $state."; break }
        if ($null -eq $days -and -not (Same-File $Exe $Backup)) {
            Copy-Item $Exe "$Backup.tmp" -Force
            Move-Item "$Backup.tmp" $Backup -Force
            Write-Output "Saved a backup of the original exe: $Backup"
        }
        Write-Head $site ([byte[]](@(0xB8) + [BitConverter]::GetBytes([uint32]$PatchDays) + @(0xC3)))
        Write-Output "Patched: $state -> patched ($PatchDays days of waves)."
    }
    "remove" {
        if ($null -eq $days) { Write-Output "Already $state."; break }
        Write-Head $site $Head
        Write-Output "Restored: $state -> vanilla ($VanillaDays days of waves)."
        if ((Test-Path $Backup) -and -not (Same-File $Exe $Backup)) {
            Write-Output "  Note: the exe isn't identical to $Backup (that backup may be from an older game version)."
        }
    }
}
