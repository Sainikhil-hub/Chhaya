# Run this as ADMINISTRATOR (right-click PowerShell -> Run as administrator):
#   powershell -ExecutionPolicy Bypass -File fix_com_port.ps1
# Cleans ghost CH340 ports (COM7/COM8) and power-cycles the live CH340 (COM9).

Write-Host "=== Ghost CH340 entries (COM7/COM8) ==="
pnputil /remove-device "USB\VID_1A86&PID_7523\5&237D5C64&0&1"
pnputil /remove-device "USB\VID_1A86&PID_7523\5&237D5C64&0&2"

Write-Host "=== Power-cycling CH340 on COM9 ==="
$id = "USB\VID_1A86&PID_7523\5&237D5C64&0&3"
try {
  Disable-PnpDevice -InstanceId $id -Confirm:$false -ErrorAction Stop
  Start-Sleep -Seconds 2
  Enable-PnpDevice  -InstanceId $id -Confirm:$false -ErrorAction Stop
  Write-Host "COM9 reset OK"
} catch {
  Write-Host "Reset failed: $($_.Exception.Message)"
  Write-Host "Unplug the board, replug it, then re-run this script."
}

Write-Host "=== Reinstalling the CH340 driver stack (device-level) ==="
# This forces Windows to rebuild the driver binding:
pnputil /restart-device $id

Write-Host "=== Test: can the port be opened? ==="
try {
  $p = New-Object System.IO.Ports.SerialPort("COM9", 115200)
  $p.Open(); $p.Close()
  Write-Host "COM9 OPENS OK - go back to Arduino IDE, reselect Tools > Port > COM9 and upload."
} catch {
  Write-Host "COM9 still failing: $($_.Exception.Message)"
  Write-Host "=> Swap the USB cable (use a known DATA cable, not charge-only),"
  Write-Host "   plug directly into the laptop (no hub), then replug the board."
}
