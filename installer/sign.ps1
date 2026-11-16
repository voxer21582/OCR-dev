param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$Thumbprint,
    [Parameter(Mandatory=$true)][string]$TimestampUrl
)
$ErrorActionPreference = 'Stop'
$file = (Resolve-Path -LiteralPath $Installer).Path
if ([IO.Path]::GetExtension($file).ToLowerInvariant() -notin @('.exe', '.dll', '.pyd')) { throw 'È richiesto un file .exe, .dll o .pyd.' }
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Impronta del certificato non valida.' }
$uri = [Uri]$TimestampUrl
if ($uri.Scheme -ne 'https') { throw 'Il servizio di marcatura temporale deve usare HTTPS.' }
$cert = Get-Item -LiteralPath "Cert:\CurrentUser\My\$Thumbprint"
if (-not $cert.HasPrivateKey) { throw 'Il certificato non dispone della chiave privata.' }
$existing = Get-AuthenticodeSignature -LiteralPath $file
if ($existing.Status -ne 'NotSigned') { throw 'Il file contiene già una firma o non è verificabile; la firma esistente non sarà sovrascritta.' }
$signature = Set-AuthenticodeSignature -LiteralPath $file -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $TimestampUrl
if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate) { throw 'Firma o marca temporale non valida.' }
Write-Output "Firma verificata: $($signature.Status); certificato: $($signature.SignerCertificate.Subject); impronta: $($signature.SignerCertificate.Thumbprint)"
