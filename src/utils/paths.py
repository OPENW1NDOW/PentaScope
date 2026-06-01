from pathlib import Path


def project_root() -> Path:
    """项目根目录（src/utils/paths.py 向上两级）"""
    return Path(__file__).resolve().parents[2]


def runs_dir() -> Path:
    return project_root() / "runs"


def logs_dir() -> Path:
    return project_root() / "logs"
