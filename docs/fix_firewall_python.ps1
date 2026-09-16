# Removes the auto-created python.exe firewall BLOCK rules.
#
# These rules are added by Windows when a "Allow python.exe ..." firewall
# popup is dismissed (clicked Cancel). Block rules always win over allow
# rules, so even with the "GhostPrint UDP 9999" allow rule present, every
# inbound UDP packet to the Chhaya app from other devices was silently
# dropped. Run once as Administrator:
#   powershell -ExecutionPolicy Bypass -File docs\fix_firewall_python.ps1
$prog = "C:\users\admin\appdata\local\programs\python\python313\python.exe"

Write-Host "Deleting python.exe block rules..."
netsh advfirewall firewall delete rule name="python.exe" program="$prog" dir=in

Write-Host "`nRemaining rules named python.exe:"
$left = netsh advfirewall firewall show rule name="python.exe" | Select-String "Rule Name"
if ($left) { $left } else { Write-Host "  (none) - fix complete" }

Write-Host "`nPort rule 'GhostPrint UDP 9999' (allow) still present:"
netsh advfirewall firewall show rule name="GhostPrint UDP 9999" | Select-String "Rule Name|Action"
