param(
    [Parameter(Mandatory=$true)][string]$ExecutableDirectory,
    [Parameter(Mandatory=$true)][string]$StopFile,
    [Parameter(Mandatory=$true)][string]$OutputFile
)
# Samples only Python processes under the selected test installation. The
# result contains counts and PIDs, never remote addresses or document data.
$prefix = (Resolve-Path -LiteralPath $ExecutableDirectory).Path.TrimEnd('\') + '\'
$seen = [System.Collections.Generic.HashSet[int]]::new()
$samples = 0
$nonloop = 0
$errors = 0
$deadline = (Get-Date).AddMinutes(20)
while ((-not (Test-Path -LiteralPath $StopFile)) -and (Get-Date) -lt $deadline) {
    try {
        $items = @(Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction Stop |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) })
        $ids = @($items | ForEach-Object { $_.ProcessId })
        foreach ($processId in $ids) { [void]$seen.Add([int]$processId) }
        if ($ids.Count -gt 0) {
            $connections = @(Get-NetTCPConnection -ErrorAction Stop | Where-Object { $_.OwningProcess -in $ids })
            $nonloop += @($connections | Where-Object { $_.RemoteAddress -notin @('0.0.0.0', '127.0.0.1', '::', '::1') }).Count
        }
        $samples++
    } catch { $errors++ }
    Start-Sleep -Seconds 2
}
[pscustomobject]@{
    samples = $samples
    process_ids = @($seen)
    nonloopback_tcp_observations = $nonloop
    errors = $errors
    stopped_by_signal = (Test-Path -LiteralPath $StopFile)
} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $OutputFile
