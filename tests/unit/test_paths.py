from src.utils.paths import project_root, runs_dir, logs_dir


def test_project_root_contains_src():
    root = project_root()
    assert (root / "src").is_dir()


def test_runs_dir_under_root():
    assert runs_dir() == project_root() / "runs"


def test_logs_dir_under_root():
    assert logs_dir() == project_root() / "logs"
