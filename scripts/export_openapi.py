import json
from pathlib import Path

from backend.app.main import app

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"


def main() -> None:
    OUTPUT_PATH.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
