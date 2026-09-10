"""
main.py -- Research Operating System web runtime entry point.

Default execution now starts the FastAPI backend used by the
React/TypeScript frontend instead of the legacy PyQt desktop UI.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    sys.stderr.write(
        "Research Operating System requires Python 3.11 or newer "
        f"(found {sys.version.split()[0]}). Please upgrade Python.\n"
    )
    sys.exit(1)

from api.app import app


def main() -> None:

    import uvicorn

    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
