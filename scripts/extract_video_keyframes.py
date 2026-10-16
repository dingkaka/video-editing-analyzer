#!/usr/bin/env python3
"""Extract fixed-interval and scene-change frames for tutorial-video review."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} was not found on PATH")
    return path


def probe(ffprobe: str, input_path: Path) -> dict:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate",
            "-of",
            "json",
            str(input_path),
        ]
    )
    data = json.loads(result.stdout)
    format_data = data.get("format", {})
    streams = data.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    return {
        "source": str(input_path),
        "format": format_data.get("format_name"),
        "duration_seconds": float(format_data["duration"]) if format_data.get("duration") else None,
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "frame_rate": video.get("avg_frame_rate") or video.get("r_frame_rate"),
        },
        "audio": {
            "present": bool(audio),
            "codec": audio.get("codec_name"),
        },
    }


SHOWINFO_TIME = re.compile(r"pts_time:([+\-0-9.eE]+)")


def parse_showinfo_timestamps(stderr: str) -> list[float]:
    return [float(match.group(1)) for match in SHOWINFO_TIME.finditer(stderr)]


def prepare_output_dir(output_dir: Path) -> None:
    (output_dir / "fixed").mkdir(parents=True, exist_ok=True)
    (output_dir / "scene").mkdir(parents=True, exist_ok=True)
    (output_dir / "frames").mkdir(parents=True, exist_ok=True)
    for pattern in ("fixed/frame_*.jpg", "scene/scene_*.jpg"):
        for path in output_dir.glob(pattern):
            path.unlink()


def extract_fixed(
    ffmpeg: str,
    input_path: Path,
    output_dir: Path,
    interval: float,
    quality: int,
) -> list[float]:
    fixed_dir = output_dir / "fixed"
    result = run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-nostats",
            "-i",
            str(input_path),
            "-vf",
            f"fps=1/{interval:g},showinfo",
            "-q:v",
            str(quality),
            str(fixed_dir / "frame_%06d.jpg"),
        ]
    )
    return parse_showinfo_timestamps(result.stderr)


def extract_scenes(
    ffmpeg: str,
    input_path: Path,
    output_dir: Path,
    scene_threshold: float,
    quality: int,
) -> list[float]:
    scene_dir = output_dir / "scene"
    result = run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-nostats",
            "-i",
            str(input_path),
            "-vf",
            f"select='gt(scene,{scene_threshold:g})',showinfo",
            "-vsync",
            "vfr",
            "-q:v",
            str(quality),
            str(scene_dir / "scene_%06d.jpg"),
        ]
    )
    return parse_showinfo_timestamps(result.stderr)


def frame_records(output_dir: Path, kind: str, timestamps: list[float]) -> list[dict]:
    paths = sorted((output_dir / kind).glob("*.jpg"))
    records = []
    for index, path in enumerate(paths):
        timestamp = timestamps[index] if index < len(timestamps) else None
        records.append(
            {
                "type": kind,
                "file": str(path.relative_to(output_dir)),
                "timestamp_seconds": timestamp,
            }
        )
    return records


def write_index(
    output_dir: Path,
    metadata: dict,
    fixed_timestamps: list[float],
    scene_timestamps: list[float],
) -> None:
    frames = []
    frames.extend(frame_records(output_dir, "fixed", fixed_timestamps))
    frames.extend(frame_records(output_dir, "scene", scene_timestamps))
    frames.sort(
        key=lambda item: (
            item["timestamp_seconds"] is None,
            item["timestamp_seconds"] if item["timestamp_seconds"] is not None else 0,
            item["type"],
        )
    )
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "frames" / "index.json").write_text(json.dumps(frames, ensure_ascii=False, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input video file")
    parser.add_argument("-o", "--output-dir", type=Path, help="Output directory; defaults to <video>.keyframes")
    parser.add_argument("--interval", type=float, default=2.0, help="Fixed-frame interval in seconds (default: 2)")
    parser.add_argument("--scene-threshold", type=float, default=0.35, help="FFmpeg scene threshold (default: 0.35)")
    parser.add_argument("--quality", type=int, default=3, help="JPEG quality scale, 2 is higher quality (default: 3)")
    parser.add_argument("--no-scenes", action="store_true", help="Skip scene-change extraction")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        print(f"Input video not found: {input_path}", file=sys.stderr)
        return 2
    if args.interval <= 0 or not 0 <= args.scene_threshold <= 1 or not 1 <= args.quality <= 31:
        print(
            "interval must be > 0, scene-threshold must be between 0 and 1, "
            "and quality must be between 1 and 31",
            file=sys.stderr,
        )
        return 2
    output_dir = (args.output_dir or input_path.with_name(input_path.name + ".keyframes")).expanduser().resolve()
    try:
        ffmpeg = require_binary("ffmpeg")
        ffprobe = require_binary("ffprobe")
        metadata = probe(ffprobe, input_path)
        prepare_output_dir(output_dir)
        fixed_timestamps = extract_fixed(ffmpeg, input_path, output_dir, args.interval, args.quality)
        scene_timestamps = []
        if not args.no_scenes:
            scene_timestamps = extract_scenes(
                ffmpeg,
                input_path,
                output_dir,
                args.scene_threshold,
                args.quality,
            )
        metadata["extraction"] = {
            "fixed_interval_seconds": args.interval,
            "scene_threshold": None if args.no_scenes else args.scene_threshold,
            "jpeg_quality": args.quality,
        }
        write_index(output_dir, metadata, fixed_timestamps, scene_timestamps)
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Video extraction failed: {exc}", file=sys.stderr)
        return 1
    print(f"Extracted keyframes to {output_dir}")
    print(f"Metadata: {output_dir / 'metadata.json'}")
    print(f"Frame index: {output_dir / 'frames' / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
