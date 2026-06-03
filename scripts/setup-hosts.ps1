# Adds operating-systems.com to the Windows hosts file (requires Administrator).
$HostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$Line = "127.0.0.1 operating-systems.com www.operating-systems.com"

if (Select-String -Path $HostsPath -Pattern "operating-systems\.com" -Quiet) {
    Write-Host "Already in hosts file:"
    Select-String -Path $HostsPath -Pattern "operating-systems\.com"
    exit 0
}

Add-Content -Path $HostsPath -Value $Line
Write-Host "Added: $Line"
Write-Host "Done. Open: https://operating-systems.com/balancer-manager"
