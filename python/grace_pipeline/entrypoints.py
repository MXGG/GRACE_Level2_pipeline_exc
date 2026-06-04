"""Canonical command-line entrypoint for installed console scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from grace_pipeline import __version__
from grace_pipeline.cli import main as legacy_main


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="GRACE Pipeline")
def main():
    """GRACE/GRACE-FO Level-2 spherical harmonic processing pipeline."""


# Reuse legacy commands while overriding commands that need normalized runtime behavior.
for _name, _cmd in legacy_main.commands.items():
    if _name not in {"info", "doctor"}:
        main.add_command(_cmd, _name)


@main.command()
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
def info(config: Optional[str], default_config: Optional[str]):
    """Show resolved runtime configuration and available data."""
    from grace_pipeline.infra.config import find_default_config, load_config
    from grace_pipeline.infra.datasets.time_index import build_time_index, detect_gfc_files

    cfg = load_config(config, default_config)
    resolved_default = default_config or find_default_config(cfg.path.ROOT)

    click.echo("\n=== GRACE Pipeline Configuration ===\n")
    click.echo(f"Version: {__version__}")
    click.echo(f"Default config: {resolved_default}")
    click.echo(f"User config: {config or '(not supplied)'}")

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
        if gfc_files:
            time_entries = build_time_index(cfg)
            click.echo(f"Time entries: {len(time_entries)}")
            if time_entries:
                click.echo(f"  First: {time_entries[0].ym}")
                click.echo(f"  Last: {time_entries[-1].ym}")
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
    click.echo(f"  Parallel: {cfg.parallel.enable} ({cfg.parallel.n_workers} workers)")


@main.command()
@click.option("-c", "--config", type=click.Path(exists=True), help="Path to user configuration JSON file.")
@click.option("-d", "--default-config", type=click.Path(exists=True), help="Path to default configuration JSON file.")
@click.option("--gui", is_flag=True, help="Also require GUI dependencies such as PySide6.")
def doctor(config: Optional[str], default_config: Optional[str], gui: bool):
    """Check Python modules, configuration files, data paths, and output writability."""
    from grace_pipeline.infra.config import load_config
    from grace_pipeline.infra.doctor import print_doctor, run_doctor

    cfg = None
    if config or default_config:
        cfg = load_config(config, default_config)
    code = print_doctor(run_doctor(cfg=cfg, default_config=default_config, check_gui=gui))
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
