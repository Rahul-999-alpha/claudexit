"""
Entry point for claudexit backend.
Used by both dev mode (python -m uvicorn) and PyInstaller binary.
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="claudexit backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
