"""Start the local FastAPI service for standalone development."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "doom.api:app",
        host=os.environ.get("DOOM_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("DOOM_API_PORT", "8000")),
        reload=False,
    )
