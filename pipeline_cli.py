from __future__ import annotations

import argparse
from pathlib import Path

from config.runtime_models import EnvironmentParameters, RadiometryParams, TwmmParams
from matching import TwmmAdapter
from radiometry import RadiometryPipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline tools for matching and radiometry layers")
    sub = parser.add_subparsers(dest="command", required=True)

    p_match = sub.add_parser("matching", help="Run TWMM matching and homography estimation")
    p_match.add_argument("--workspace-root", type=Path, required=True)
    p_match.add_argument("--twmm-root", type=Path, required=True)
    p_match.add_argument("--rgb-dir", type=Path, required=True)
    p_match.add_argument("--thermal-tiff-dir", type=Path, required=True)
    p_match.add_argument("--thermal-preview-dir", type=Path, required=True)
    p_match.add_argument("--output-dir", type=Path, required=True)
    p_match.add_argument("--patch-size", type=int, default=40)
    p_match.add_argument("--search-radius", type=int, default=60)
    p_match.add_argument("--level-max", type=int, default=4)
    p_match.add_argument("--crop-width", type=int, default=1024)
    p_match.add_argument("--crop-height", type=int, default=1024)
    p_match.add_argument("--crop-offset-x", type=int, default=0)
    p_match.add_argument("--crop-offset-y", type=int, default=0)
    p_match.add_argument("--thermal-scale", type=float, default=1.0)
    p_match.add_argument("--visible-scale", type=float, default=1.0)
    p_match.add_argument("--outlier-threshold-px", type=float, default=2.0)
    p_match.add_argument("--min-inliers", type=int, default=8)
    p_match.add_argument("--homography-condition-max", type=float, default=1e6)
    p_match.add_argument("--max-pairs", type=int, default=None)

    p_rad = sub.add_parser("radiometry", help="Run thermal radiometry extraction")
    p_rad.add_argument("--workspace-root", type=Path, required=True)
    p_rad.add_argument("--metadata-json", type=Path, required=True)
    p_rad.add_argument("--thermal-tiff-dir", type=Path, required=True)
    p_rad.add_argument("--output-dir", type=Path, required=True)
    p_rad.add_argument("--ambient-temperature-celsius", type=float, required=False)
    p_rad.add_argument("--relative-humidity-percent", type=float, required=False)
    p_rad.add_argument("--emissivity-ratio", type=float, required=False)
    p_rad.add_argument("--distance-to-target-m", type=float, required=False)
    p_rad.add_argument("--reflected-temperature-celsius", type=float, required=False)
    p_rad.add_argument("--atmospheric-pressure-hpa", type=float, required=False)
    p_rad.add_argument("--environment-source", type=str, default="manual")
    p_rad.add_argument("--environment-source-ref", type=str, default=None)
    p_rad.add_argument("--processing-version", type=str, default="radiometry.v1")
    p_rad.add_argument("--input-is-temperature", action="store_true")
    p_rad.add_argument("--raw-to-temperature-scale", type=float, default=0.04)
    p_rad.add_argument("--raw-to-temperature-offset", type=float, default=-273.15)
    p_rad.add_argument("--max-frames", type=int, default=None)

    return parser


def run_matching(args: argparse.Namespace) -> None:
    params = TwmmParams(
        patch_size=args.patch_size,
        search_radius=args.search_radius,
        level_max=args.level_max,
        crop_size=(args.crop_width, args.crop_height),
        crop_offset=(args.crop_offset_x, args.crop_offset_y),
        scale={"thermal": args.thermal_scale, "visible": args.visible_scale},
        outlier_threshold_px=args.outlier_threshold_px,
        min_inliers=args.min_inliers,
        homography_condition_max=args.homography_condition_max,
    )

    adapter = TwmmAdapter(workspace_root=args.workspace_root, twmm_root=args.twmm_root)
    results = adapter.match_batch_from_dirs(
        rgb_dir=args.rgb_dir,
        thermal_tiff_dir=args.thermal_tiff_dir,
        thermal_preview_dir=args.thermal_preview_dir,
        params=params,
        output_dir=args.output_dir,
        max_pairs=args.max_pairs,
    )
    print(f"matching completed: {len(results)} pairs")


def run_radiometry(args: argparse.Namespace) -> None:
    env = EnvironmentParameters(
        ambient_temperature_celsius=args.ambient_temperature_celsius,
        relative_humidity_percent=args.relative_humidity_percent,
        emissivity_ratio=args.emissivity_ratio,
        distance_to_target_m=args.distance_to_target_m,
        reflected_temperature_celsius=args.reflected_temperature_celsius,
        atmospheric_pressure_hpa=args.atmospheric_pressure_hpa,
        source=args.environment_source,
        source_ref=args.environment_source_ref,
    )

    params = RadiometryParams(
        metadata_json_path=args.metadata_json,
        processing_version=args.processing_version,
        input_is_temperature=args.input_is_temperature,
        raw_to_temperature_scale=args.raw_to_temperature_scale,
        raw_to_temperature_offset=args.raw_to_temperature_offset,
    )

    pipeline = RadiometryPipeline(workspace_root=args.workspace_root, params=params)
    results = pipeline.process_batch(
        thermal_tiff_dir=args.thermal_tiff_dir,
        env=env,
        output_dir=args.output_dir,
        max_frames=args.max_frames,
    )
    print(f"radiometry completed: {len(results)} frames")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "matching":
        run_matching(args)
    elif args.command == "radiometry":
        run_radiometry(args)
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
