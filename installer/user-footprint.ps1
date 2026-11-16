<#
.SYNOPSIS
  Impronta del profilo utente prima e dopo OCR2 (REQ-102, REQ-104). Sola lettura.
.DESCRIPTION
  -Out <file>            scrive l'elenco di file e cartelle sotto %LOCALAPPDATA% e sotto
                         %APPDATA%\Microsoft\Windows\Start Menu e i NOMI delle chiavi sotto
                         HKCU\Software (mai i valori). Unico file scritto: quello di -Out.
  -Compare <prima> <dopo> confronta due impronte e stampa solo le differenze:
                         "+" presente solo dopo, "-" presente solo prima,
                         "~" file con dimensione diversa.
  Senza -Out l'impronta e' stampata a video. Le cartelle non leggibili sono riportate come
  DENIED e non fermano la lettura. I collegamenti/giunzioni sono elencati ma non seguiti.
  Righe: RADICE<TAB>TIPO<TAB>percorso[<TAB>dimensione]; RADICE = LOCALAPPDATA | STARTMENU | HKCU;
  TIPO = D cartella, F file, K chiave, DENIED. Ordine ordinale: due impronte identiche
  producono file identici. Solo PowerShell integrato (Windows PowerShell 5.1).
  I parametri -LocalAppData, -StartMenu e -RegistryRoot servono alle prove su cartelle finte.
#>
[CmdletBinding(DefaultParameterSetName = 'Snapshot')]
param(
    [Parameter(ParameterSetName = 'Snapshot')][string]$Out,
    [Parameter(ParameterSetName = 'Compare', Mandatory = $true)][string]$Compare,
    [Parameter(ParameterSetName = 'Compare', Mandatory = $true, Position = 0)][string]$Dopo,
    [Parameter(ParameterSetName = 'Snapshot')][string]$LocalAppData = $env:LOCALAPPDATA,
    [Parameter(ParameterSetName = 'Snapshot')][string]$StartMenu = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu'),
    [Parameter(ParameterSetName = 'Snapshot')][string]$RegistryRoot = 'HKCU:\Software'
)
$ErrorActionPreference = 'Stop'
$Header = '# OCR2 impronta utente v1'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Add-FolderLines {
    param([string]$Label, [string]$Root, [System.Collections.Generic.List[string]]$Lines)
    if (-not [System.IO.Directory]::Exists($Root)) { return }
    $stack = New-Object System.Collections.Generic.Stack[string]
    $stack.Push('')
    while ($stack.Count -gt 0) {
        $relative = $stack.Pop()
        $full = if ($relative -eq '') { $Root } else { [System.IO.Path]::Combine($Root, $relative) }
        try {
            $directories = [System.IO.Directory]::GetDirectories($full)
            $files = [System.IO.Directory]::GetFiles($full)
        } catch {
            $Lines.Add("$Label`tDENIED`t$relative")
            continue
        }
        foreach ($directory in $directories) {
            $name = [System.IO.Path]::GetFileName($directory)
            $child = if ($relative -eq '') { $name } else { "$relative\$name" }
            $Lines.Add("$Label`tD`t$child")
            $isLink = $false
            try {
                $isLink = ([System.IO.File]::GetAttributes($directory) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
            } catch { }
            if (-not $isLink) { $stack.Push($child) }
        }
        foreach ($file in $files) {
            $name = [System.IO.Path]::GetFileName($file)
            $child = if ($relative -eq '') { $name } else { "$relative\$name" }
            try { $size = (New-Object System.IO.FileInfo($file)).Length } catch { $size = -1 }
            $Lines.Add("$Label`tF`t$child`t$size")
        }
    }
}

function Add-RegistryLines {
    param([string]$Root, [System.Collections.Generic.List[string]]$Lines)
    $prefix = 'HKCU:\'
    if (-not $Root.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "RegistryRoot deve iniziare con HKCU:\"
    }
    $base = $Root.Substring($prefix.Length).Trim('\')
    $top = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($base, $false)
    if ($null -eq $top) { return }
    $stack = New-Object System.Collections.Generic.Stack[object]
    $stack.Push(@{ Key = $top; Path = '' })
    while ($stack.Count -gt 0) {
        $item = $stack.Pop()
        try { $names = $item.Key.GetSubKeyNames() } catch { $Lines.Add("HKCU`tDENIED`t$($item.Path)"); $item.Key.Close(); continue }
        foreach ($name in $names) {
            $child = if ($item.Path -eq '') { $name } else { "$($item.Path)\$name" }
            $Lines.Add("HKCU`tK`t$child")
            try {
                $sub = $item.Key.OpenSubKey($name, $false)
                if ($null -ne $sub) { $stack.Push(@{ Key = $sub; Path = $child }) }
            } catch { $Lines.Add("HKCU`tDENIED`t$child") }
        }
        $item.Key.Close()
    }
}

function Read-Footprint {
    param([string]$Path)
    if (-not [System.IO.File]::Exists($Path)) { throw "File non trovato: $Path" }
    $table = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::Ordinal)
    foreach ($line in [System.IO.File]::ReadAllLines($Path, $Utf8)) {
        if ($line.Length -eq 0 -or $line.StartsWith('#')) { continue }
        $parts = $line.Split("`t")
        if ($parts.Length -lt 3) { continue }
        $key = $parts[0] + "`t" + $parts[1] + "`t" + $parts[2]
        $table[$key] = if ($parts.Length -ge 4) { $parts[3] } else { '' }
    }
    return ,$table
}

if ($PSCmdlet.ParameterSetName -eq 'Compare') {
    $before = Read-Footprint $Compare
    $after = Read-Footprint $Dopo
    $changes = New-Object System.Collections.Generic.List[string]
    foreach ($key in $after.Keys) {
        if (-not $before.ContainsKey($key)) {
            $suffix = if ($after[$key] -ne '') { "`t" + $after[$key] } else { '' }
            $changes.Add("+ $key$suffix")
        } elseif ($before[$key] -ne $after[$key]) {
            $changes.Add("~ $key`t$($before[$key]) -> $($after[$key])")
        }
    }
    foreach ($key in $before.Keys) {
        if (-not $after.ContainsKey($key)) {
            $suffix = if ($before[$key] -ne '') { "`t" + $before[$key] } else { '' }
            $changes.Add("- $key$suffix")
        }
    }
    $array = $changes.ToArray()
    # Ordine per percorso (dopo il segno), poi per segno: righe dello stesso elemento vicine.
    [Array]::Sort($array, [StringComparer]::Ordinal)
    Write-Output "# Differenze: $($array.Length) (+ solo dopo, - solo prima, ~ dimensione diversa)"
    foreach ($line in $array) { Write-Output $line }
    exit 0
}

$all = New-Object System.Collections.Generic.List[string]
Add-FolderLines 'LOCALAPPDATA' $LocalAppData $all
Add-FolderLines 'STARTMENU' $StartMenu $all
Add-RegistryLines $RegistryRoot $all
$array = $all.ToArray()
[Array]::Sort($array, [StringComparer]::Ordinal)
$output = New-Object System.Collections.Generic.List[string]
$output.Add($Header)
$output.AddRange($array)
if ($Out) {
    [System.IO.File]::WriteAllLines($Out, $output.ToArray(), $Utf8)
    Write-Host ("Impronta scritta in {0}: {1} voci" -f $Out, $array.Length)
} else {
    foreach ($line in $output) { Write-Output $line }
}
exit 0
