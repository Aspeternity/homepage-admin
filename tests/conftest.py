from __future__ import annotations

import os
import shutil
import tempfile
import sys
from pathlib import Path

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
