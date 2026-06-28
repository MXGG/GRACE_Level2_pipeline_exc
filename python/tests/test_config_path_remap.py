import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import grace_pipeline.core.config as config_mod
from grace_pipeline.infra.config import load_config


class ConfigPathRemapTest(unittest.TestCase):
    def _restore_runtime(self, old_attrs, old_env):
        for name, value in old_attrs.items():
            if value is None:
                try:
                    delattr(sys, name)
                except AttributeError:
                    pass
            else:
                setattr(sys, name, value)
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_windows_root_paths_are_remapped_to_runtime_root(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td) / "runtime_root"
            runtime_root.mkdir(parents=True, exist_ok=True)
            user_cfg_path = Path(td) / "user.json"
            default_cfg_path = Path(td) / "default.json"

            default_cfg_path.write_text("{}", encoding="utf-8")

            source_root = r"G:\GRACE_Level2_pipeline_exc"
            user_cfg = {
                "path": {
                    "ROOT": source_root,
                    "GFC": source_root + r"\data\GRACE\SLR\IGG-SLR-DORR",
                    "OUTPUT": source_root + r"\output\SLR",
                    "DDK": source_root + r"\data\DDK",
                },
                "inversion": {
                    "lowdeg": {
                        "files": {
                            "C20": source_root + r"\data\GRACE\LowDegree\TN-14_C30_C20_GSFC_SLR.txt",
                        }
                    }
                },
            }
            user_cfg_path.write_text(json.dumps(user_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            cfg = load_config(
                user_config=user_cfg_path,
                default_config=default_cfg_path,
                root_dir=runtime_root,
            )

            rr = str(runtime_root.resolve())
            self.assertEqual(cfg.path.ROOT, rr)
            self.assertEqual(cfg.path.GFC, str(runtime_root / "data" / "GRACE" / "SLR" / "IGG-SLR-DORR"))
            self.assertEqual(cfg.path.OUTPUT, str(runtime_root / "output" / "SLR"))
            self.assertEqual(
                cfg.inversion.lowdeg["files"]["C20"],
                str(runtime_root / "data" / "GRACE" / "LowDegree" / "TN-14_C30_C20_GSFC_SLR.txt"),
            )

    def test_frozen_runtime_uses_install_env_and_bundle_fallbacks(self):
        names = ["frozen", "_MEIPASS", "executable"]
        old_attrs = {name: getattr(sys, name, None) for name in names}
        env_names = ["GRACE_L2_HOME", "GRACE_L2_DATA", "GRACE_L2_OUTPUT"]
        old_env = {name: os.environ.get(name) for name in env_names}
        try:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                install_root = base / "install"
                bundle_root = base / "bundle"
                env_data = install_root / "data"
                env_output = install_root / "output"
                env_data.mkdir(parents=True)
                env_output.mkdir()
                (bundle_root / "cfg").mkdir(parents=True)
                (bundle_root / "data" / "Boundary").mkdir(parents=True)
                (bundle_root / "cfg" / "default.json").write_text("{}", encoding="utf-8")
                exe_dir = install_root / "dist"
                exe_dir.mkdir(parents=True)

                sys.frozen = True
                sys._MEIPASS = str(bundle_root)
                sys.executable = str(exe_dir / "grace-pipeline-gui.exe")
                os.environ["GRACE_L2_HOME"] = str(install_root)
                os.environ["GRACE_L2_DATA"] = str(env_data)
                os.environ["GRACE_L2_OUTPUT"] = str(env_output)

                self.assertEqual(config_mod.get_root_dir(), install_root.resolve())
                self.assertEqual(config_mod.get_data_dir(), env_data.resolve())
                self.assertEqual(config_mod.get_output_dir(), env_output.resolve())
                self.assertEqual(config_mod.find_default_config(), (bundle_root / "cfg" / "default.json").resolve())
                self.assertEqual(config_mod.get_config_dir(), (install_root / "configs").resolve())
        finally:
            self._restore_runtime(old_attrs, old_env)

    def test_frozen_runtime_can_use_grace_l2_ini_without_env(self):
        names = ["frozen", "_MEIPASS", "executable"]
        old_attrs = {name: getattr(sys, name, None) for name in names}
        env_names = ["GRACE_L2_HOME", "GRACE_L2_DATA", "GRACE_L2_OUTPUT"]
        old_env = {name: os.environ.get(name) for name in env_names}
        try:
            for name in env_names:
                os.environ.pop(name, None)
            with tempfile.TemporaryDirectory() as td:
                install_root = Path(td) / "install"
                data_dir = install_root / "data"
                output_dir = install_root / "output"
                dist_dir = install_root / "dist"
                data_dir.mkdir(parents=True)
                output_dir.mkdir()
                dist_dir.mkdir()
                (install_root / "grace-l2.ini").write_text(
                    "[Paths]\n"
                    f"HomeDir={install_root}\n"
                    f"DataDir={data_dir}\n"
                    f"OutputDir={output_dir}\n",
                    encoding="utf-8",
                )

                sys.frozen = True
                sys.executable = str(dist_dir / "grace-pipeline-gui.exe")
                if hasattr(sys, "_MEIPASS"):
                    delattr(sys, "_MEIPASS")

                self.assertEqual(config_mod.get_root_dir(), install_root.resolve())
                self.assertEqual(config_mod.get_data_dir(), data_dir.resolve())
                self.assertEqual(config_mod.get_output_dir(), output_dir.resolve())
        finally:
            self._restore_runtime(old_attrs, old_env)


if __name__ == "__main__":
    unittest.main()
