from __future__ import annotations

import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RebrandContractTests(unittest.TestCase):
    def test_new_package_cli_and_custom_node_asset_exist(self) -> None:
        package = importlib.import_module("comfy_ltx_loop")
        self.assertEqual(package.__version__, "0.1.0")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('comfy-ltx-loop = "comfy_ltx_loop.cli:main"', pyproject)
        self.assertTrue(
            (ROOT / "comfy_nodes" / "comfy_ltx_loop" / "web" / "comfy_ltx_loop.js").is_file()
        )

