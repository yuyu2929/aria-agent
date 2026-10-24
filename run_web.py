"""启动 Web 仪表盘：python run_web.py [--port 8000]"""
from __future__ import annotations

import sys

import uvicorn

from webapp.server import create_app

if __name__ == "__main__":
    port = 8000
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
