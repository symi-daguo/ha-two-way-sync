Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('temp_brands\custom_integrations\ha_two_way_sync\icon.png')
Write-Host 'Icon dimensions:' $img.Width 'x' $img.Height
$img.Dispose()

$logo = [System.Drawing.Image]::FromFile('temp_brands\custom_integrations\ha_two_way_sync\logo.png')
Write-Host 'Logo dimensions:' $logo.Width 'x' $logo.Height
$logo.Dispose()