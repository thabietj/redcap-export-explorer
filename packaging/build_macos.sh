#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$PWD/build/pyinstaller-config}"
mkdir -p "$PYINSTALLER_CONFIG_DIR"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean redcap_export_explorer.spec
APP="dist/REDCap Export Explorer.app"
PKG="dist/REDCap-Export-Explorer-0.3.1-macOS-arm64.pkg"
test -d "$APP"
STAGE="$(mktemp -d /private/tmp/redcap-installer.XXXXXX)"
COPYFILE_DISABLE=1 ditto --norsrc "$APP" "$STAGE/REDCap Export Explorer.app"
xattr -cr "$STAGE/REDCap Export Explorer.app"
codesign --force --deep --sign - "$STAGE/REDCap Export Explorer.app"
codesign --verify --deep --strict "$STAGE/REDCap Export Explorer.app"
pkgbuild --component "$STAGE/REDCap Export Explorer.app" --install-location /Applications --identifier org.redcapexportexplorer.app --version 0.3.1 "$PKG"
echo "$PKG"
