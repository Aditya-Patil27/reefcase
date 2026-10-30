from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from reefcase.core.config import Settings
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.segmenter import build_segmenter

__all__ = ["pseudo_label_frames"]

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def pseudo_label_frames(
    *,
    in_dir: Path,
    out_dir: Path,
    source: str,
    licence: str,
    limit: int | None = None,
    segmenter: str = "sam3_local",
) -> int:
    settings = Settings(_env_file=None, segmenter=segmenter)
    backend = build_segmenter(settings)
    labels_dir = out_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.jsonl"

    done = _existing_frames(manifest_path)
    written = 0

    for frame_path in sorted(in_dir.iterdir()):
        if frame_path.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        if limit is not None and written >= limit:
            break
        if frame_path.name in done and (labels_dir / f"{frame_path.stem}.png").exists():
            continue

        image = np.asarray(Image.open(frame_path).convert("RGB"), dtype=np.uint8)
        mask = backend.segment(image)
        mask_path = labels_dir / f"{frame_path.stem}.png"
        Image.fromarray(mask, mode="L").save(mask_path, format="PNG")
        cover = {klass.value: value for klass, value in cover_from_mask(mask).items()}
        record = {
            "frame": frame_path.name,
            "mask": str(mask_path.relative_to(out_dir).as_posix()),
            "source": source,
            "licence": licence,
            "cover": cover,
        }
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        written += 1

    return written


def _existing_frames(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    frames: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            item = json.loads(payload)
            frame = item.get("frame")
            if isinstance(frame, str):
                frames.add(frame)
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    parser.add_argument("--source", default="coralscapes_trainval")
    parser.add_argument("--licence", default="Apache-2.0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--segmenter", default="sam3_local")
    args = parser.parse_args()

    written = pseudo_label_frames(
        in_dir=args.in_dir,
        out_dir=args.out_dir,
        source=args.source,
        licence=args.licence,
        limit=args.limit,
        segmenter=args.segmenter,
    )
    print(f"wrote {written} labels to {args.out_dir}")


if __name__ == "__main__":
    main()
