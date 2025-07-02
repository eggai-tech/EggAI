"""Run tests for the Frontend Agent."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    test_path = repo_root / "agents" / "frontend"
    subprocess.run([sys.executable, "-m", "pytest", str(test_path), "-s"], check=False, cwd=repo_root)


if __name__ == "__main__":
    main()
