"""Canonical command-line interface for GRACE Pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from grace_pipeline import __version__
from grace_pipeline.infra.runtime import limit_blas_threads, recommend_workers


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="GRACE Pipeline")
def main():
    """GRACE/GRACE-FO Level-2 spherical harmonic processing pipeline."""


@main.command()
def gui():
    """Launch the graphical interface."""
    limit_blas_threads()
    from grace_pipeline.gui import start_gui

    start_gui()


HSAF_EXPERIMENT_ENGINE_CHOICES = [
    "adaptive_parity_hsaf_v1",
    "sampling_pseudomoire_v1",
    "modal_adaptive_v1",
    "modal_adaptive_latband_v1",
    "multichannel_v1",
    "modal_adaptive_v2",
    "modal_adaptive_latband_v2",
    "multichannel_v2",
    "modal_adaptive_v3",
    "modal_adaptive_latband_v3",
    "multichannel_v3",
    "demod_profile_v1",
    "demod_multichannel_v1",
    "bundle_template_v1",
    "bundle_template_multichannel_v1",
    "sh_orderwise_v1",
    "sh_multichannel_v1",
    "sh_demod_v1",
    "sh_demod_multichannel_v1",
    "sh_orbit_orderwise_v1",
    "sh_orbit_multichannel_v1",
    "sh_orbit_demod_v1",
    "sh_orbit_demod_multichannel_v1",
    "sh_orbit_carrier_demod_v1",
    "sh_orbit_carrier_demod_multichannel_v1",
    "carrier_removed_hsaf_v1",
    "carrier_removed_multichannel_v1",
    "orbit_bundle_v1",
    "orbit_bundle_multichannel_v1",
    "bundle_phase_demod_v1",
    "bundle_phase_demod_multichannel_v1",
    "pseudo_moire_operator_v1",
    "pseudo_moire_operator_multichannel_v1",
    "sampling_operator_v1",
    "sampling_operator_multichannel_v1",
    "sampling_inversion_v1",
    "sampling_inversion_multichannel_v1",
]


def _parse_jobs_option(_ctx, _param, value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() == "auto":
        return "auto"
    try:
        parsed = int(text)
    except ValueError as exc:
        raise click.BadParameter("must be an integer worker count or 'auto'") from exc
    if parsed < 1:
        raise click.BadParameter("must be >= 1")
    return parsed


def _apply_runtime_overrides(cfg, output: Optional[str], start: Optional[str], end: Optional[str], jobs, no_parallel: bool, *, gui: bool = False):
    if output:
        cfg._raw.setdefault("path", {})["OUTPUT"] = output
        cfg.path.OUTPUT = output
    if start:
        cfg._raw.setdefault("time", {})["start_ym"] = start
        cfg.time.start_ym = start
    if end:
        cfg._raw.setdefault("time", {})["end_ym"] = end
        cfg.time.end_ym = end

    if no_parallel:
        cfg._raw.setdefault("parallel", {})["enable"] = False
        cfg.parallel.enable = False
        cfg.parallel.n_workers = 1
        return cfg

    if jobs is None:
        return cfg

    frozen_cap = 0
    try:
        frozen_cap = int(getattr(cfg, "perf", {}).get("frozen_max_workers", 0) or 0)
    except Exception:
        frozen_cap = 0
    selected = recommend_workers(
        configured_workers=jobs,
        task_type="pipeline",
        gui=gui,
        frozen_max_workers=frozen_cap or None,
    )
    cfg._raw.setdefault("parallel", {})["enable"] = selected > 1
    cfg._raw.setdefault("parallel", {})["nWorkers"] = selected
    cfg.parallel.enable = selected > 1
    cfg.parallel.n_workers = selected
    return cfg


@main.command()
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
@click.option("-o", "--output", type=click.Path(), help="Override output directory.")
@click.option("--start", type=str, help="Start month, YYYY-MM.")
@click.option("--end", type=str, help="End month, YYYY-MM.")
@click.option("-j", "--jobs", callback=_parse_jobs_option, help="Override parallel workers: integer or auto. Omit to use config.")
@click.option("--no-parallel", is_flag=True, help="Disable parallel processing.")
@click.option("--show-runtime", is_flag=True, help="Print detected runtime resources before running.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose traceback on error.")
def run(config: Optional[str], default_config: Optional[str], output: Optional[str], start: Optional[str], end: Optional[str], jobs, no_parallel: bool, show_runtime: bool, verbose: bool):
    """Run the full GRACE processing pipeline."""
    from grace_pipeline.app.pipeline import run_pipeline
    from grace_pipeline.infra.config import load_config
    from grace_pipeline.infra.runtime import detect_runtime_context

    cfg = load_config(config, default_config)
    cfg = _apply_runtime_overrides(cfg, output, start, end, jobs, no_parallel)

    if show_runtime:
        ctx = detect_runtime_context()
        click.echo("Runtime context:")
        for key, value in ctx.to_dict().items():
            click.echo(f"  {key}: {value}")
        click.echo(f"  selected_workers: {cfg.parallel.n_workers}")

    try:
        result = run_pipeline(cfg)
        click.echo("\nPipeline completed successfully!")
        click.echo(f"Output directory: {result.paths.root}")
        click.echo(f"Processed {len(result.time_entries)} months")
        click.echo(f"Products: {', '.join(result.plan['order'])}")
    except Exception as exc:
        click.echo(f"\nError: {exc}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
def info(config: Optional[str], default_config: Optional[str]):
    """Show resolved runtime configuration and available data."""
    from grace_pipeline.infra.config import find_default_config, load_config
    from grace_pipeline.infra.datasets.time_index import build_time_index, detect_gfc_files
    from grace_pipeline.infra.runtime import detect_runtime_context, recommend_workers

    cfg = load_config(config, default_config)
    resolved_default = default_config or find_default_config(cfg.path.ROOT)
    runtime = detect_runtime_context()
    selected_workers = recommend_workers(getattr(cfg.parallel, "n_workers", "auto"))

    click.echo("\n=== GRACE Pipeline Configuration ===\n")
    click.echo(f"Version: {__version__}")
    click.echo(f"Default config: {resolved_default}")
    click.echo(f"User config: {config or '(not supplied)'}")
    click.echo(f"Runtime: platform={runtime.platform}, slurm={runtime.is_slurm}, available_cpus={runtime.available_cpus}, selected_workers={selected_workers}")

    click.echo("\nPaths:")
    click.echo(f"  ROOT: {cfg.path.ROOT}")
    click.echo(f"  GFC directory: {cfg.path.GFC}")
    click.echo(f"  Output: {cfg.path.OUTPUT}")
    click.echo(f"  DDK data: {cfg.filter.ddk.data_dir}")
    click.echo(f"  Boundary: {cfg.path.BOUNDARY}")

    click.echo("\nTime range:")
    click.echo(f"  Auto-detect: {cfg.time.auto_detect_gfc}")
    click.echo(f"  Start: {cfg.time.start_ym}")
    click.echo(f"  End: {cfg.time.end_ym}")

    if Path(cfg.path.GFC).exists():
        gfc_files = detect_gfc_files(cfg.path.GFC, cfg.time.product_type, cfg.time.file_ext)
        click.echo(f"\nAvailable GFC files: {len(gfc_files)}")
        entries = build_time_index(cfg)
        click.echo(f"Time entries after configured range filter: {len(entries)}")
        if entries:
            click.echo(f"  First: {entries[0].ym}")
            click.echo(f"  Last: {entries[-1].ym}")
    else:
        click.echo(f"\nGFC directory not found: {cfg.path.GFC}")

    click.echo("\nGrid:")
    click.echo(f"  Lon: {cfg.grid.lon[0]} to {cfg.grid.lon[1]}, dlon={cfg.grid.dlon}")
    click.echo(f"  Lat: {cfg.grid.lat[0]} to {cfg.grid.lat[1]}, dlat={cfg.grid.dlat}")

    click.echo("\nFilters:")
    click.echo(f"  Gaussian: {cfg.filter.gaussian.enable} (r={cfg.filter.gaussian.radius_km} km)")
    click.echo(f"  P4M6: {cfg.filter.p4m6.enable}")
    click.echo(f"  DDK: {cfg.filter.ddk.enable} ({cfg.filter.ddk.type})")
    click.echo(f"  HSAF: {cfg.filter.hankel.enable}")

    click.echo("\nProcessing:")
    click.echo(f"  Max degree: {cfg.inversion.Lmax}")
    click.echo(f"  Remove mean: {cfg.inversion.remove_mean}")
    click.echo(f"  Parallel: {cfg.parallel.enable} ({cfg.parallel.n_workers} configured; {selected_workers} recommended)")


@main.command()
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
@click.option("--gui", is_flag=True, help="Require GUI dependencies such as PySide6.")
def doctor(config: Optional[str], default_config: Optional[str], gui: bool):
    """Check modules, config files, data paths, output writability, and runtime resources."""
    from grace_pipeline.infra.config import load_config
    from grace_pipeline.infra.doctor import print_doctor, run_doctor
    from grace_pipeline.infra.runtime import detect_runtime_context, recommend_workers

    cfg = load_config(config, default_config) if (config or default_config) else None
    code = print_doctor(run_doctor(cfg=cfg, default_config=default_config, check_gui=gui))
    ctx = detect_runtime_context()
    configured = getattr(getattr(cfg, "parallel", None), "n_workers", "auto") if cfg is not None else "auto"
    click.echo(f"[OK  ] runtime.available_cpus: {ctx.available_cpus}")
    click.echo(f"[OK  ] runtime.recommended_workers: {recommend_workers(configured, gui=gui)}")
    if code:
        sys.exit(code)


@main.command(name="filter-gfc-ddk")
@click.option("--input-dir", required=True, type=click.Path(exists=True, file_okay=False), help="Directory containing input .gfc files.")
@click.option("--output-dir", required=True, type=click.Path(file_okay=False), help="Output root directory.")
@click.option("--ddk-data-dir", required=True, type=click.Path(exists=True, file_okay=False), help="Directory containing DDK binary kernels.")
@click.option("--ddk", "ddk_types", multiple=True, default=("DDK3", "DDK4", "DDK5"), help="DDK type to apply. Can be repeated.")
@click.option("--lmax", type=int, default=96, show_default=True, help="Maximum SH degree to read and write.")
@click.option("--skip-existing", is_flag=True, help="Do not overwrite existing output files.")
def filter_gfc_ddk(input_dir: str, output_dir: str, ddk_data_dir: str, ddk_types: tuple[str, ...], lmax: int, skip_existing: bool):
    """Apply DDK filters to GFC coefficients and write filtered GFC files."""
    from grace_pipeline.app.ddk_gfc import filter_gfc_directory

    results = filter_gfc_directory(input_dir=input_dir, output_root=output_dir, ddk_types=ddk_types, ddk_data_dir=ddk_data_dir, lmax=lmax, overwrite=not skip_existing)
    for result in results:
        click.echo(f"{result.ddk_type}: wrote {result.files_written} files to {result.output_dir}")


@main.command(name="hsaf-experiments")
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
@click.option("--stack-dir", type=click.Path(exists=True, file_okay=False), help="Directory containing stacks.")
@click.option("--month", "months", multiple=True, help="Representative month to test, YYYY-MM.")
@click.option("--engine", "engines", multiple=True, type=click.Choice(HSAF_EXPERIMENT_ENGINE_CHOICES), help="Experimental HSAF engine to run. Can be supplied multiple times.")
@click.option("--input-tag", type=click.Choice(["RAW", "P4M6"], case_sensitive=False), default="P4M6", show_default=True)
@click.option("--outdir", type=click.Path(), help="Optional output directory.")
def hsaf_experiments(config: Optional[str], default_config: Optional[str], stack_dir: Optional[str], months: tuple[str, ...], engines: tuple[str, ...], input_tag: str, outdir: Optional[str]):
    """Run small-sample HSAF prototype experiments against DDK4."""
    from grace_pipeline.app.hsaf_experiments import run_hsaf_experiments
    from grace_pipeline.infra.config import load_config

    limit_blas_threads()
    cfg = load_config(config, default_config)
    stack_root = Path(stack_dir) if stack_dir else Path(cfg.path.OUTPUT) / "local" / "stacks"
    result_dir = run_hsaf_experiments(cfg=cfg, stack_dir=stack_root, outdir=Path(outdir) if outdir else None, months=list(months) if months else None, engines=list(engines) if engines else None, input_tag=input_tag)
    click.echo(f"Experiment outputs written to: {result_dir}")


@main.command(name="grace-l1b-fetch")
@click.option("--release", type=click.Choice(["RL02", "RL03"], case_sensitive=False), default="RL03", show_default=True)
@click.option("--month", help="Month stamp for RL03, format YYYY-MM.")
@click.option("--day", help="Day stamp for RL02, format YYYY-MM-DD.")
@click.option("--output-dir", type=click.Path(), default=str(Path("outputs") / "local" / "tmp" / "grace_l1b"), show_default=True)
@click.option("--product", "products", multiple=True, help="Optional filename prefixes to extract from the archive.")
@click.option("--list-only", is_flag=True, help="List archive members after download without extracting.")
def grace_l1b_fetch(release: str, month: Optional[str], day: Optional[str], output_dir: str, products: tuple[str, ...], list_only: bool):
    """Fetch GRACE Level-1B bundles from GFZ ISDC."""
    from grace_pipeline.app.grace_l1b_fetch import build_gfz_target, download_target, extract_selected_members, list_archive_members

    target = build_gfz_target(release=release, month=month, day=day)
    out_dir = Path(output_dir)
    archive_path = download_target(target, out_dir)
    click.echo(f"Downloaded: {archive_path}")
    if list_only:
        for name in list_archive_members(archive_path, limit=120):
            click.echo(name)
        return
    if products:
        extracted = extract_selected_members(archive_path, out_dir / target.stamp, prefixes=products)
        click.echo(f"Extracted {len(extracted)} file(s) to: {out_dir / target.stamp}")
        for path in extracted[:40]:
            click.echo(str(path))


@main.command()
@click.argument("template", type=click.Choice(["default", "minimal", "full"]))
@click.option("-o", "--output", type=click.Path(), default="config.json", help="Output filename.")
def init(template: str, output: str):
    """Initialize a new configuration file."""
    templates = {
        "default": {
            "path": {"ROOT": "${ROOT}", "GFC": "${ROOT}/data/GRACE/GSM", "OUTPUT": "${ROOT}/outputs", "DDK": "${ROOT}/data/DDK"},
            "time": {"auto_detect_gfc": True, "start_ym": "2002-04", "end_ym": "2020-12"},
            "grid": {"lon": [-179.5, 179.5], "lat": [-89.5, 89.5], "dlon": 1.0, "dlat": 1.0},
            "inversion": {"Lmax": 60, "remove_mean": True},
            "filter": {"gaussian": {"enable": True, "radius_km": 300}, "p4m6": {"enable": True, "poly_deg": 4, "m_start": 6}, "ddk": {"enable": True, "type": "DDK4"}, "hankel": {"enable": False}},
            "parallel": {"enable": True, "nWorkers": 4},
        },
        "minimal": {"path": {"GFC": "./data/GRACE/GSM", "OUTPUT": "./outputs"}, "inversion": {"Lmax": 60}, "parallel": {"nWorkers": 4}},
        "full": {
            "_comment": "GRACE Level-2 Processing Pipeline Configuration",
            "path": {"ROOT": "${ROOT}", "GFC": "${ROOT}/data/GRACE/GSM", "OUTPUT": "${ROOT}/outputs", "AUX": "${ROOT}/data/Aux", "DDK": "${ROOT}/data/DDK", "BOUNDARY": "${ROOT}/data/Boundary"},
            "time": {"auto_detect_gfc": True, "start_ym": "2002-04", "end_ym": "2020-12", "product_type": "GSM", "file_ext": ".gfc"},
            "grid": {"lon": [-179.5, 179.5], "lat": [-89.5, 89.5], "dlon": 1.0, "dlat": 1.0, "unit": "mmEWH"},
            "inversion": {"Lmax": 60, "remove_mean": True},
            "filter": {"gaussian": {"enable": True, "radius_km": 300}, "p4m6": {"enable": True, "poly_deg": 4, "m_start": 6}, "fan": {"enable": False, "radius1_km": 300, "radius2_km": 300}, "ddk": {"enable": True, "type": "DDK4"}, "hankel": {"enable": True, "variant": "global", "mode": "profile", "params": {"N": 30, "P": 10, "K": 6, "J": 1}}, "pre_hankel_input": "P4M6"},
            "io": {"save_monthly_mat": True, "save_stack_mat": True, "export_txt": True, "resume": False},
            "parallel": {"enable": True, "nWorkers": 8},
        },
    }
    with open(output, "w", encoding="utf-8") as f:
        json.dump(templates[template], f, indent=2)
    click.echo(f"Created configuration file: {output}")
    click.echo(f"Template: {template}")


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    main()
