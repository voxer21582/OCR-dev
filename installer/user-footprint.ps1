[CmdletBinding(DefaultParameterSetName='Capture')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Capture')][string]$Out,
    [Parameter(Mandatory=$true,ParameterSetName='Compare')][ValidateCount(2,2)][string[]]$Compare
)
$ErrorActionPreference = 'Stop'
if ($PSCmdlet.ParameterSetName -eq 'Compare') {
    $before = Get-Content -LiteralPath $Compare[0] -Encoding UTF8
    $after = Get-Content -LiteralPath $Compare[1] -Encoding UTF8
    Compare-Object -ReferenceObject $before -DifferenceObject $after | ForEach-Object {
        if ($_.SideIndicator -eq '=>') { '+ ' + $_.InputObject } else { '- ' + $_.InputObject }
    }
    return
}

if (-not $env:LOCALAPPDATA -or -not $env:APPDATA) { throw 'Cartelle utente non disponibili.' }
$roots = @(
    [pscustomobject]@{ Label='LOCALAPPDATA'; Path=$env:LOCALAPPDATA },
    [pscustomobject]@{ Label='START_MENU'; Path=(Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu') }
)
$entries = [System.Collections.Generic.List[string]]::new()
$enumerationErrors = @()
foreach ($root in $roots) {
    if (Test-Path -LiteralPath $root.Path -PathType Container) {
        $prefix = [IO.Path]::GetFullPath($root.Path).TrimEnd('\') + '\'
        Get-ChildItem -LiteralPath $root.Path -Force -Recurse -ErrorAction SilentlyContinue -ErrorVariable +enumerationErrors | ForEach-Object {
            $full = $_.FullName
            if ($full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                $kind = if ($_.PSIsContainer) { 'DIR' } else { 'FILE' }
                $entries.Add("$($root.Label)|$kind|$($full.Substring($prefix.Length))")
            }
        }
    }
}
Get-ChildItem -LiteralPath 'HKCU:\Software' -ErrorAction Stop | ForEach-Object { $entries.Add("HKCU_SOFTWARE|KEY|$($_.PSChildName)") }
$entries | Sort-Object -Unique | Set-Content -LiteralPath $Out -Encoding UTF8
if ($enumerationErrors.Count) {
    Write-Warning "Rilevati $($enumerationErrors.Count) elementi non leggibili: l'inventario è incompleto."
}
