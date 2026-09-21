"""CLI entry point for importing archived Markdown reports."""
from __future__ import annotations

import argparse
from pathlib import Path

from knowledge_workbench.store import import_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Wire Mesh reports into the knowledge workbench")
    parser.add_argument("archive_dir", help="Directory containing archived Markdown reports")
    parser.add_argument(
        "--db",
        default="knowledge_workbench/knowledge.db",
        help="SQLite database path (default: knowledge_workbench/knowledge.db)",
    )
    args = parser.parse_args()
    result = import_directory(Path(args.db), Path(args.archive_dir))
    print("scanned={scanned} imported={imported} skipped={skipped}".format(**result))


if __name__ == "__main__":
    main()
