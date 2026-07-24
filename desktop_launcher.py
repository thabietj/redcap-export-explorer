"""Desktop entry point used by the optional PyInstaller build."""
from __future__ import annotations
import os, socket, sys, threading, time, webbrowser
from pathlib import Path


def resource_path(name: str) -> Path:
    root=Path(getattr(sys,"_MEIPASS",Path(__file__).parent))
    return root/name


def available_port() -> str:
    """Ask the operating system for an unused localhost port."""
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1",0))
        return str(probe.getsockname()[1])


def main() -> None:
    """Start a localhost-only Streamlit process and open the system browser."""
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"]="false"
    os.environ["STREAMLIT_SERVER_ADDRESS"]="127.0.0.1"
    port=os.environ.get("REDCAP_EXPLORER_PORT") or available_port()
    threading.Thread(target=lambda:(time.sleep(1.5),webbrowser.open(f"http://127.0.0.1:{port}")),daemon=True).start()
    from streamlit.web import cli as stcli
    sys.argv=["streamlit","run",str(resource_path("app.py")),"--global.developmentMode=false","--server.address=127.0.0.1",f"--server.port={port}","--browser.gatherUsageStats=false","--server.fileWatcherType=none"]
    raise SystemExit(stcli.main())


if __name__=="__main__": main()
