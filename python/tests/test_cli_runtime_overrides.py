import unittest
from types import SimpleNamespace

import click

from grace_pipeline.cli import _apply_runtime_overrides, _parse_jobs_option
from grace_pipeline.infra.runtime import recommend_workers


class CliRuntimeOverridesTest(unittest.TestCase):
    def _cfg(self, *, enable=False, workers=1):
        return SimpleNamespace(
            _raw={"parallel": {"enable": enable, "nWorkers": workers}},
            path=SimpleNamespace(OUTPUT=""),
            time=SimpleNamespace(start_ym="", end_ym=""),
            perf={},
            parallel=SimpleNamespace(enable=enable, n_workers=workers),
        )

    def test_omitted_jobs_preserves_disabled_parallel_config(self):
        cfg = self._cfg(enable=False, workers=1)

        _apply_runtime_overrides(cfg, None, None, None, jobs=None, no_parallel=False)

        self.assertFalse(cfg.parallel.enable)
        self.assertEqual(cfg.parallel.n_workers, 1)
        self.assertEqual(cfg._raw["parallel"], {"enable": False, "nWorkers": 1})

    def test_explicit_auto_jobs_enables_recommended_workers(self):
        cfg = self._cfg(enable=False, workers=1)

        _apply_runtime_overrides(cfg, None, None, None, jobs="auto", no_parallel=False)

        expected = recommend_workers("auto")
        self.assertEqual(cfg.parallel.n_workers, expected)
        self.assertEqual(cfg.parallel.enable, expected > 1)

    def test_invalid_jobs_option_is_rejected(self):
        with self.assertRaises(click.BadParameter):
            _parse_jobs_option(None, None, "not-an-int")


if __name__ == "__main__":
    unittest.main()
