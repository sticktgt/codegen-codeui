from __future__ import annotations

import uvicorn

from codeui.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "codeui.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    main()
