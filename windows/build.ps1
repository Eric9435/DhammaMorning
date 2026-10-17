$ErrorActionPreference = "Stop"
python -m pip install -r windows/requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name DhammaMorning windows/app.py
Write-Output "Generated dist/DhammaMorning.exe"
