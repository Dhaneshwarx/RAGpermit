# Starts the MCP server. It works from any folder:   python C:\path\to\PermitRAG\run_mcp_server.py
# (src/mcp_server.py then moves into the project folder by itself.)
#
# The server reads the person from the environment variable PERMITRAG_TOKEN. Start it with a token:
#     $env:PERMITRAG_TOKEN = python -m src.issue_token Premkumar 3600
#     python run_mcp_server.py
# An AI app starts it for you; see the README.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
