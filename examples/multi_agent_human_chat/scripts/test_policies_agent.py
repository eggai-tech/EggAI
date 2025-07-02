"""Run tests for the Policies Agent."""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    test_path = repo_root / "agents" / "policies"
    subprocess.run([sys.executable, "-m", "pytest", str(test_path), "-s"], check=False, cwd=repo_root)


if __name__ == "__main__":
    main()
