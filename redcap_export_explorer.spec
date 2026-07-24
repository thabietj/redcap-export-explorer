# Cross-platform PyInstaller recipe. Build on each target operating system.
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# The app script is executed dynamically by Streamlit, so its imports must be
# named here. Standard PyInstaller hooks collect each package's native pieces.
datas=collect_data_files("streamlit")
for package in ["streamlit","pandas","openpyxl","pydantic","pyarrow"]:
    datas += copy_metadata(package)
datas += [("app.py","."),("src/redcap_explorer","src/redcap_explorer"),(".streamlit",".streamlit")]
binaries=[]
hiddenimports=["pandas","numpy","openpyxl","charset_normalizer","pydantic","yaml","pyarrow"]
hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("redcap_explorer")

a=Analysis(["desktop_launcher.py"],pathex=[".","src"],binaries=binaries,datas=datas,hiddenimports=hiddenimports)
pyz=PYZ(a.pure)

if sys.platform == "darwin":
    exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name="REDCap Export Explorer",console=False,target_arch="arm64")
    collected=COLLECT(exe,a.binaries,a.datas,strip=False,name="REDCap Export Explorer")
    app=BUNDLE(collected,name="REDCap Export Explorer.app",bundle_identifier="org.redcapexportexplorer.app",info_plist={
        "CFBundleName":"REDCap Export Explorer","CFBundleDisplayName":"REDCap Export Explorer",
        "CFBundleShortVersionString":"0.3.1","CFBundleVersion":"0.3.1",
        "NSHighResolutionCapable":True,"LSMinimumSystemVersion":"12.0"
    })
else:
    exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name="REDCapExportExplorer",console=False,upx=False)
