import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from llm_health.config import expand_leading_tilde, resolve_store_path, set_hub_path


class HubConfigTests(unittest.TestCase):
    def test_expand_leading_tilde_only(self):
        path = expand_leading_tilde("~/health-data")
        self.assertTrue(str(path).startswith(str(Path.home())))
        self.assertIn("health-data", str(path))

    def test_config_hub_path_resolves_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            hub = Path(tmp) / "health-hub"
            set_hub_path(hub, config_path)
            self.assertEqual(json.loads(config_path.read_text())["hub_path"], str(hub))
            old = os.environ.get("LLM_HEALTH_CONFIG")
            os.environ["LLM_HEALTH_CONFIG"] = str(config_path)
            try:
                self.assertEqual(resolve_store_path(), hub)
            finally:
                if old is None:
                    os.environ.pop("LLM_HEALTH_CONFIG", None)
                else:
                    os.environ["LLM_HEALTH_CONFIG"] = old

    def test_cli_config_hub_path_init(self):
        repo = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo / "src")
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            hub = Path(tmp) / "health"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "config",
                    "hub-path",
                    str(hub),
                    "--config-path",
                    str(config_path),
                    "--init",
                    "--accept-risk",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((hub / "agreement.json").exists())
            self.assertTrue((hub / "manifest.json").exists())
            show = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_health",
                    "config",
                    "show",
                    "--config-path",
                    str(config_path),
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            self.assertIn(str(hub), show.stdout)


if __name__ == "__main__":
    unittest.main()
