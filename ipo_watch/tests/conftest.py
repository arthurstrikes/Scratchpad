
import pytest


@pytest.fixture(autouse=True)
def _never_touch_the_real_history_branch(monkeypatch):
    """Tests call run.main() with Telegram settings from the environment; without this a
    test could push stub files to the repository's real history branch (it did once, on
    12 Nov 2026, and two datasets had to be restored)."""
    monkeypatch.setenv("IPOWATCH_NO_HISTORY", "1")
