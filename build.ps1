$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (python -c "import randomdrumsheet; print(randomdrumsheet.__version__)").Trim()
python -m PyInstaller RandomDrumSheet.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$app = Join-Path "dist" "RandomDrumSheet"
Copy-Item "README.txt" (Join-Path $app "README.txt") -Force
$licenses = Join-Path $app "licenses"
New-Item -ItemType Directory -Force $licenses | Out-Null
Copy-Item "randomdrumsheet\assets\fonts\*.txt" $licenses -Force

$zip = Join-Path "dist" "RandomDrumSheet-$version-windows.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $app -DestinationPath $zip
Write-Host "Done: $zip"
