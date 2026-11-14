from __future__ import annotations

import os
import shutil
import tempfile
import sys
import time
from pathlib import Path

import pytest
from itsdangerous import TimestampSigner


@pytest.fixture(autouse=True)
def monotonic_session_clock(monkeypatch):
    # VM wall-clock corrections must not invalidate a token between two test
    # requests. Keep expiry checking active against an advancing test clock.
    wall, monotonic = time.time(), time.monotonic()
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda _self: int(wall + time.monotonic() - monotonic))

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_ROOT = Path(tempfile.mkdtemp(prefix="homepage-admin-tests-"))
CONFIG = TEST_ROOT / "config"
DATA = TEST_ROOT / "data"
CONFIG.mkdir()
DATA.mkdir()
for source in (ROOT / "example-config").glob("*.yaml"):
    shutil.copy2(source, CONFIG / source.name)

# Add a secret-bearing service to verify that the normal form does not expose it.
(CONFIG / "services.yaml").write_text(
    """---
- Core:
    - Jellyfin:
        icon: jellyfin.png
        href: https://jellyfin.example
        widget:
          type: jellyfin
          url: https://jellyfin.example
          key: super-secret-key
""",
    encoding="utf-8",
)

os.environ["HOMEPAGE_CONFIG_DIR"] = str(CONFIG)
os.environ["ADMIN_DATA_DIR"] = str(DATA)
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["ADMIN_PASSWORD_HASH"] = ""
os.environ["SESSION_SECRET"] = "test-session-secret-that-is-long-enough"
os.environ["HOMEPAGE_URL"] = "http://homepage.local"
os.environ["ADMIN_ALLOWED_HOSTS"] = "*"
os.environ["WIDGET_SCHEMA_AUTO_SYNC"] = "false"
