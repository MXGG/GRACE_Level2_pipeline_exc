"""
Command-line interface for GRACE pipeline.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from grace_pipeline.infra.runtime import limit_blas_threads

@click.group()
@click.version_option(version="1.0.0", prog_name="GRACE Pipeline")
def main():
    """GRACE Level-2 Satellite Gravity Data Processing Pipeline.
    
    Process GRACE/GRACE-FO spherical harmonic coefficients into
    filtered gridded equivalent water height (EWH) products.
    """
    pass


@main.command()
def gui():
    """Launch the graphical interface."""
    limit_blas_threads()
    from grace_pipeline.gui import start_gui
    start_gui()


@main.command()
@click.option(
    '-c', '--config',
    type=click.Path(exists=True),
    help='Path to user configuration JSON file'
)
@click.option(
    '-d', '--default-config',
    type=click.Path(exists=True),
    help='Path to default configuration JSON file'
)
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Override output directory'
)
@click.option(
    '--start', 
    type=str,
    help='Start date (YYYY-MM format)'
)
@click.option(
    '--end',
    type=str,
    help='End date (YYYY-MM format)'
)
@click.option(
    '-j', '--jobs',
    type=int,
    default=1,
    help='Number of parallel jobs'
)
@click.option(
    '--no-parallel',
    is_flag=True,
    help='Disable parallel processing'
)
@click.option(
    '-v', '--verbose',
    is_flag=True,
    help='Verbose output'
)
def run(
    config: Optional[str],
    default_config: Optional[str],
    output: Optional[str],
    start: Optional[str],
    end: Optional[str],
    jobs: int,
    no_parallel: bool,
    verbose: bool,
):
    """Run the full GRACE processing pipeline.
    
    Examples:
    
        grace-pipeline run -c cfg/user.json
        
        grace-pipeline run --start 2002-04 --end 2020-12 -j 8
    """
    from grace_pipeline.infra.config import load_config, merge_configs
    from grace_pipeline.app.pipeline import run_pipeline
    
    # Load configuration
    cfg = load_config(config, default_config)
    
    # Apply overrides
    if output:
        cfg._raw['path']['OUTPUT'] = output
        cfg.path.OUTPUT = output
    
    if start:
        cfg._raw['time']['start_ym'] = start
        cfg.time.start_ym = start
    
    if end:
        cfg._raw['time']['end_ym'] = end
        cfg.time.end_ym = end
    
    if no_parallel:
        cfg._raw['parallel']['enable'] = False
        cfg.parallel.enable = False
    elif jobs > 1:
        cfg._raw['parallel']['enable'] = True
        cfg._raw['parallel']['nWorkers'] = jobs
        cfg.parallel.enable = True
        cfg.parallel.n_workers = jobs
    
    # Run pipeline
    try:
        pipeline_result = run_pipeline(cfg)
        click.echo(f"\nPipeline completed successfully!")
        click.echo(f"Output directory: {pipeline_result.paths.root}")
        click.echo(f"Processed {len(pipeline_result.time_entries)} months")
        click.echo(f"Products: {', '.join(pipeline_result.plan['order'])}")
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option(
    '-c', '--config',
    type=click.Path(exists=True),
    help='Path to configuration file'
)
def info(config: Optional[str]):
    """Show pipeline configuration and available data.
    
    Examples:
    
        grace-pipeline info
        
        grace-pipeline info -c cfg/user.json
    """
    from grace_pipeline.infra.config import load_config
    from grace_pipeline.infra.datasets.time_index import build_time_index, detect_gfc_files
    
    cfg = load_config(config)
    
    click.echo("\n=== GRACE Pipeline Configuration ===\n")
    
    click.echo("Paths:")
    click.echo(f"  GFC directory: {cfg.path.GFC}")
    click.echo(f"  Output: {cfg.path.OUTPUT}")
    click.echo(f"  DDK data: {cfg.filter.ddk.data_dir}")
    
    click.echo("\nTime range:")
    click.echo(f"  Auto-detect: {cfg.time.auto_detect_gfc}")
    click.echo(f"  Start: {cfg.time.start_ym}")
    click.echo(f"  End: {cfg.time.end_ym}")
    
    # Detect available data
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
    click.echo(f"  Gaussian: {cfg.filter.gaussian.enable} (r={cfg.filter.gaussian.radius_km}km)")
    click.echo(f"  P4M6: {cfg.filter.p4m6.enable}")
    click.echo(f"  DDK: {cfg.filter.ddk.enable} ({cfg.filter.ddk.type})")
    click.echo(f"  HSAF: {cfg.filter.hankel.enable}")
    
    click.echo("\nProcessing:")
    click.echo(f"  Max degree: {cfg.inversion.Lmax}")
    click.echo(f"  Remove mean: {cfg.inversion.remove_mean}")
    click.echo(f"  Parallel: {cfg.parallel.enable} ({cfg.parallel.n_workers} workers)")
    
    click.echo()


@main.command(name="filter-gfc-ddk")
@click.option(
    "--input-dir",
    "input_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing input .gfc files.",
)
@click.option(
    "--output-dir",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output root directory. One subdirectory is created per DDK type.",
)
@click.option(
    "--ddk-data-dir",
    "ddk_data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing GRACE-filter-master DDK binary kernels.",
)
@click.option(
    "--ddk",
    "ddk_types",
    multiple=True,
    default=("DDK3", "DDK4", "DDK5"),
    help="DDK type to apply. Can be repeated. Defaults to DDK3, DDK4, DDK5.",
)
@click.option(
    "--lmax",
    type=int,
    default=96,
    show_default=True,
    help="Maximum spherical-harmonic degree to read and write.",
)
@click.option(
    "--skip-existing",
    is_flag=True,
    help="Do not overwrite existing output files.",
)
def filter_gfc_ddk(
    input_dir: str,
    output_dir: str,
    ddk_data_dir: str,
    ddk_types: tuple[str, ...],
    lmax: int,
    skip_existing: bool,
):
    """Apply DDK filters to GFC coefficients and write filtered GFC files."""
    from grace_pipeline.app.ddk_gfc import filter_gfc_directory

    try:
        results = filter_gfc_directory(
            input_dir=input_dir,
            output_root=output_dir,
            ddk_types=ddk_types,
            ddk_data_dir=ddk_data_dir,
            lmax=lmax,
            overwrite=not skip_existing,
        )
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)

    for result in results:
        click.echo(
            f"{result.ddk_type}: wrote {result.files_written} files to {result.output_dir}"
        )


@main.command(name="hsaf-experiments")
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True),
    help="Path to user configuration JSON file",
)
@click.option(
    "-d",
    "--default-config",
    type=click.Path(exists=True),
    help="Path to default configuration JSON file",
)
@click.option(
    "--stack-dir",
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing P4M6/HSAF/DDK4 stacks. Defaults to <OUTPUT>/local/stacks.",
)
@click.option(
    "--month",
    "months",
    multiple=True,
    help="Representative month to test (YYYY-MM). Can be supplied multiple times.",
)
@click.option(
    "--engine",
    "engines",
    multiple=True,
    type=click.Choice([
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
    ]),
    help="Experimental HSAF engine to run. Can be supplied multiple times.",
)
@click.option(
    "--input-tag",
    type=click.Choice(["RAW", "P4M6"], case_sensitive=False),
    default="P4M6",
    show_default=True,
    help="Input stack used for experimental HSAF filtering.",
)
@click.option(
    "--outdir",
    type=click.Path(),
    help="Optional output directory. Defaults to output/local/compare/hsaf_experiments/<run_id>.",
)
def hsaf_experiments(
    config: Optional[str],
    default_config: Optional[str],
    stack_dir: Optional[str],
    months: tuple[str, ...],
    engines: tuple[str, ...],
    input_tag: str,
    outdir: Optional[str],
):
    """Run small-sample HSAF prototype experiments against DDK4."""
    from grace_pipeline.infra.config import load_config
    from grace_pipeline.app.hsaf_experiments import run_hsaf_experiments

    limit_blas_threads()
    cfg = load_config(config, default_config)
    stack_root = Path(stack_dir) if stack_dir else Path(cfg.path.OUTPUT) / "local" / "stacks"
    result_dir = run_hsaf_experiments(
        cfg=cfg,
        stack_dir=stack_root,
        outdir=Path(outdir) if outdir else None,
        months=list(months) if months else None,
        engines=list(engines) if engines else None,
        input_tag=input_tag,
    )
    click.echo(f"Experiment outputs written to: {result_dir}")


@main.command(name="grace-l1b-fetch")
@click.option(
    "--release",
    type=click.Choice(["RL02", "RL03"], case_sensitive=False),
    default="RL03",
    show_default=True,
    help="GFZ ISDC L1B release to fetch.",
)
@click.option("--month", help="Month stamp for RL03, format YYYY-MM.")
@click.option("--day", help="Day stamp for RL02, format YYYY-MM-DD.")
@click.option(
    "--output-dir",
    type=click.Path(),
    default=str(Path("output") / "local" / "tmp" / "grace_l1b"),
    show_default=True,
    help="Directory used for downloads and optional extraction.",
)
@click.option(
    "--product",
    "products",
    multiple=True,
    help="Optional filename prefixes to extract from the archive, e.g. GNV1B GPS1B KBR1B.",
)
@click.option("--list-only", is_flag=True, help="List archive members after download without extracting.")
def grace_l1b_fetch(
    release: str,
    month: Optional[str],
    day: Optional[str],
    output_dir: str,
    products: tuple[str, ...],
    list_only: bool,
):
    """Fetch GRACE Level-1B bundles from GFZ ISDC."""
    from grace_pipeline.app.grace_l1b_fetch import (
        build_gfz_target,
        download_target,
        extract_selected_members,
        list_archive_members,
    )

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
@click.argument('template', type=click.Choice(['default', 'minimal', 'full']))
@click.option(
    '-o', '--output',
    type=click.Path(),
    default='config.json',
    help='Output filename'
)
def init(template: str, output: str):
    """Initialize a new configuration file.
    
    Templates:
    
        default - Standard configuration with common settings
        
        minimal - Minimum required settings only
        
        full - All options with documentation
    
    Examples:
    
        grace-pipeline init default -o my_config.json
    """
    import json
    
    templates = {
        'default': {
            "path": {
                "ROOT": "${ROOT}",
                "GFC": "${ROOT}/data/GRACE/GSM",
                "OUTPUT": "${ROOT}/output",
                "DDK": "${ROOT}/data/DDK"
            },
            "time": {
                "auto_detect_gfc": True,
                "start_ym": "2002-04",
                "end_ym": "2020-12"
            },
            "grid": {
                "lon": [-179.5, 179.5],
                "lat": [-89.5, 89.5],
                "dlon": 1.0,
                "dlat": 1.0
            },
            "inversion": {
                "Lmax": 60,
                "remove_mean": True
            },
            "filter": {
                "gaussian": {"enable": True, "radius_km": 300},
                "p4m6": {"enable": True, "poly_deg": 4, "m_start": 6},
                "ddk": {"enable": True, "type": "DDK4"},
                "hankel": {"enable": False}
            },
            "parallel": {
                "enable": True,
                "nWorkers": 4
            }
        },
        'minimal': {
            "path": {
                "GFC": "./data/GSM",
                "OUTPUT": "./output"
            },
            "inversion": {"Lmax": 60}
        },
        'full': {
            "_comment": "GRACE Level-2 Processing Pipeline Configuration",
            "path": {
                "ROOT": "${ROOT}",
                "GFC": "${ROOT}/data/GRACE/GSM",
                "OUTPUT": "${ROOT}/output",
                "AUX": "${ROOT}/data/Aux",
                "DDK": "${ROOT}/data/DDK",
                "BOUNDARY": "${ROOT}/data/Boundary"
            },
            "time": {
                "auto_detect_gfc": True,
                "start_ym": "2002-04",
                "end_ym": "2020-12",
                "product_type": "GSM",
                "file_ext": ".gfc"
            },
            "grid": {
                "lon": [-179.5, 179.5],
                "lat": [-89.5, 89.5],
                "dlon": 1.0,
                "dlat": 1.0,
                "unit": "mmEWH"
            },
            "inversion": {
                "Lmax": 60,
                "remove_mean": True,
                "lowdeg": {
                    "enable": True,
                    "replace_C20": True,
                    "replace_C10": True,
                    "files": {
                        "C20": "${ROOT}/data/GRACE/LowDegree/TN-14_C30_C20_GSFC_SLR.txt",
                        "DEGREE1": "${ROOT}/data/GRACE/LowDegree/TN-13_GEOC_CSR_RL06.txt"
                    }
                },
                "gia": {
                    "enable": False,
                    "file": "${ROOT}/data/GRACE/GIA/GIA_Stokes_ICE-6G_D.txt"
                }
            },
            "filter": {
                "gaussian": {"enable": True, "radius_km": 300},
                "p4m6": {"enable": True, "poly_deg": 4, "m_start": 6},
                "fan": {"enable": False, "radius1_km": 300, "radius2_km": 300},
                "ddk": {"enable": True, "type": "DDK4"},
                "hankel": {
                    "enable": True,
                    "variant": "global",
                    "mode": "profile",
                    "params": {"N": 30, "P": 10, "K": 6, "J": 1}
                },
                "pre_hankel_input": "P4M6"
            },
            "io": {
                "save_monthly_mat": True,
                "save_stack_mat": True,
                "export_txt": True,
                "resume": False
            },
            "parallel": {
                "enable": True,
                "nWorkers": 8
            }
        }
    }
    
    config = templates[template]
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    click.echo(f"Created configuration file: {output}")
    click.echo(f"Template: {template}")


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
