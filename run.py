"""CortexFlow startup script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "cortexflow.api.server:create_app",
        factory=True,
        host="0.0.0.0",
        port=9000,
        reload=True,
    )
