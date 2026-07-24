# Installer builds

Installers must be built on their target operating system because PyInstaller does not cross-compile.

## macOS Apple Silicon

From the project root, install the desktop dependencies and run:

```bash
python -m pip install -e '.[desktop]'
sh packaging/build_macos.sh
```

This creates `dist/REDCap-Export-Explorer-0.3.1-macOS-arm64.pkg`. The script applies an ad-hoc application signature for local testing; the installer itself remains unsigned. Public distribution requires Developer ID Application/Installer signing and Apple notarization.

## Windows x64

Install Python 3.11 x64 and Inno Setup 6, then run in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[desktop]"
.\packaging\build_windows.ps1
```

This creates `dist\installer\REDCap-Export-Explorer-0.3.1-Windows-x64-Setup.exe`. Public distribution should use an Authenticode code-signing certificate.
