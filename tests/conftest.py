import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_llm():
    with patch("src._helpers._llm") as mock:
        mock.return_value = '{"tasks": []}'
        yield mock


@pytest.fixture
def mock_router():
    with patch("src.llm_router.get_router") as mock:
        mock_instance = MagicMock()
        mock_instance.call.return_value = {"content": "mocked response"}
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def tmp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "src", "api", "handlers"))
        os.makedirs(os.path.join(tmpdir, "src", "models"))
        os.makedirs(os.path.join(tmpdir, "tests"))
        os.makedirs(os.path.join(tmpdir, "node_modules", "fake"))
        os.makedirs(os.path.join(tmpdir, ".git"))

        sample_files = {
            "src/api/handlers/auth.py": "def login():\n    pass\n\ndef logout():\n    pass\n",
            "src/api/handlers/users.py": "def get_user():\n    pass\n\ndef create_user():\n    pass\n",
            "src/api/handlers/orders.py": "def create_order():\n    pass\n",
            "src/models/user.py": "class User:\n    pass\n",
            "tests/test_auth.py": "def test_login():\n    pass\n",
            "pyproject.toml": "[tool.pytest]\n",
            "README.md": "# Test Project\n",
        }

        for filepath, content in sample_files.items():
            full_path = os.path.join(tmpdir, filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        yield tmpdir


@pytest.fixture
def clean_budget():
    from src.token_budget import TokenBudgetManager
    manager = TokenBudgetManager(
        per_task_budget_usd=1.00,
        per_run_budget_usd=100.00,
        daily_budget_usd=1000.00,
    )
    yield manager


@pytest.fixture
def tmp_db():
    """Provide a TimpsDB backed by a temp file for testing."""
    import tempfile
    from src.persistence import TimpsDB
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = TimpsDB(db_path=db_path)
    yield db
    db.close()
    os.unlink(db_path)
