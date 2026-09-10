from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_live_services() -> None:
    dashboard = Path(__file__).resolve().parents[1] / "dashboard.py"
    app = AppTest.from_file(str(dashboard)).run(timeout=30)

    assert not app.exception
