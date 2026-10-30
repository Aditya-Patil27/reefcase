"""Train ReefStudent (U-Net, EfficientNet-B0) on class-map labels (Story 7.2).

The manifest's masks are either SAM 3 pseudo-labels (the distilled student) or the
Coralscapes human labels mapped to six classes (the supervised student); pixels at 255
(unlabelled) are skipped.

Runs on a Kaggle T4:
    python ml/kaggle/train_student.py --manifest labels/manifest.jsonl --frames frames/ --out out/

Writes ``reefstudent.pt`` (a ``state_dict`` that ``reefcase.vision.student`` loads),
``curve.json`` (loss and val mIoU per epoch) and ``metrics.json`` (best epoch, per-class IoU).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from reefcase.core.schemas import MASK_INDEX

__all__ = ["ManifestItem", "iou_from_confusion", "split_manifest", "train_from_manifest"]

_CLASSES = len(MASK_INDEX)
_IGNORE = 255


@dataclass(frozen=True, slots=True)
class ManifestItem:
    frame: str
    source: str
    source_group: str
    mask: str = ""


def split_manifest(
    items: list[ManifestItem], val_ratio: float = 0.1
) -> tuple[list[ManifestItem], list[ManifestItem]]:
    groups: dict[str, list[ManifestItem]] = {}
    for item in items:
        groups.setdefault(item.source_group, []).append(item)
    group_keys = sorted(groups)
    val_target = max(1, round(len(group_keys) * val_ratio))
    val_groups = set(group_keys[:val_target])
    train: list[ManifestItem] = []
    val: list[ManifestItem] = []
    for key in group_keys:
        bucket = val if key in val_groups else train
        bucket.extend(groups[key])
    return train, val


def iou_from_confusion(confusion: np.ndarray) -> tuple[dict[str, float], float]:
    """Per-class IoU (by ``MASK_INDEX``) and their mean, from a [target, prediction] matrix."""
    inter = np.diag(confusion).astype(np.float64)
    union = confusion.sum(axis=0) + confusion.sum(axis=1) - inter
    per_class = {
        klass.value: float(inter[index] / union[index]) if union[index] else 1.0
        for klass, index in MASK_INDEX.items()
    }
    return per_class, float(np.mean(list(per_class.values())))


def train_from_manifest(
    *,
    manifest_path: Path,
    frames_dir: Path,
    out_dir: Path,
    epochs: int = 30,
    batch_size: int = 8,
    lr: float = 1e-3,
) -> dict[str, object]:
    import segmentation_models_pytorch as smp
    import torch
    from torch.nn import functional

    from reefcase.vision.student import model_input_size

    items = _read_manifest(manifest_path)
    train_items, val_items = split_manifest(items)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda"

    def load(subset: list[ManifestItem]) -> tuple[torch.Tensor, torch.Tensor]:
        from PIL import Image

        images, masks = [], []
        for item in subset:
            image = Image.open(frames_dir / item.frame).convert("RGB")
            height, width = model_input_size(image.height, image.width)
            image = image.resize((width, height), Image.Resampling.BILINEAR)
            mask = Image.open(manifest_path.parent / item.mask).resize(
                (width, height), Image.Resampling.NEAREST
            )
            images.append(torch.from_numpy(np.asarray(image)).permute(2, 0, 1))
            masks.append(torch.from_numpy(np.asarray(mask, dtype=np.int64)))
        return torch.stack(images), torch.stack(masks)

    # About 2.6 GB of uint8 at 512x1024: the whole corpus fits in RAM, so no DataLoader.
    train_x, train_y = load(train_items)
    val_x, val_y = load(val_items)
    print(f"train {len(train_items)} frames, val {len(val_items)} frames", flush=True)

    model = smp.Unet("efficientnet-b0", encoder_weights="imagenet", classes=_CLASSES).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    steps = epochs * ((len(train_items) + batch_size - 1) // batch_size)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=lr, total_steps=steps)
    scaler = torch.amp.GradScaler()

    best_val_miou = -1.0
    best_epoch = 0
    per_class_iou: dict[str, float] = {}
    history: list[dict[str, float | int]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        order = torch.randperm(len(train_x))
        total = 0.0
        for start in range(0, len(order), batch_size):
            index = order[start : start + batch_size]
            x = train_x[index].to(device).float() / 255.0
            y = train_y[index].to(device)
            if torch.rand(1).item() < 0.5:
                x, y = x.flip(-1), y.flip(-1)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = functional.cross_entropy(model(x), y, ignore_index=_IGNORE)
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total += loss.item() * len(index)

        model.eval()
        confusion = torch.zeros(_CLASSES * _CLASSES, dtype=torch.int64, device=device)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
            for start in range(0, len(val_x), batch_size):
                x = val_x[start : start + batch_size].to(device).float() / 255.0
                y = val_y[start : start + batch_size].to(device)
                pred = model(x).argmax(1)
                keep = y != _IGNORE
                confusion += torch.bincount(
                    y[keep] * _CLASSES + pred[keep], minlength=_CLASSES * _CLASSES
                )
        epoch_iou, val_miou = iou_from_confusion(confusion.view(_CLASSES, _CLASSES).cpu().numpy())
        train_loss = total / len(train_x)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_miou": val_miou})
        print(f"epoch {epoch}: loss {train_loss:.4f} val mIoU {val_miou:.4f}", flush=True)
        if val_miou > best_val_miou:
            best_val_miou, best_epoch, per_class_iou = val_miou, epoch, epoch_iou
            torch.save(model.state_dict(), out_dir / "reefstudent.pt")

    result = {
        "best_epoch": best_epoch,
        "best_val_miou": best_val_miou,
        "val_target": f"{manifest_path.parent.name} labels on held-out dive sites",
        "train_frames": len(train_items),
        "val_frames": len(val_items),
        "val_groups": sorted({item.source_group for item in val_items}),
        "per_class_iou": per_class_iou,
        "history": history,
    }
    (out_dir / "curve.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _read_manifest(path: Path) -> list[ManifestItem]:
    items: list[ManifestItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        frame = str(payload["frame"])
        items.append(
            ManifestItem(
                frame=frame,
                source=str(payload.get("source", "unknown")),
                source_group=str(payload.get("source_group", _derive_group(frame))),
                mask=str(payload.get("mask", "")),
            )
        )
    return items


def _derive_group(frame: str) -> str:
    # Coralscapes frames are `siteNN_<seq>_<frame>_...`: group by dive site, so no
    # site appears on both sides of the split.
    return frame.split("_", maxsplit=1)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    metrics = train_from_manifest(
        manifest_path=args.manifest,
        frames_dir=args.frames,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    print(
        f"best epoch={metrics['best_epoch']} val_miou={metrics['best_val_miou']:.3f} "
        f"train={metrics['train_frames']} val={metrics['val_frames']}"
    )
    print("per-class IoU:")
    for name, value in metrics["per_class_iou"].items():
        print(f"- {name}: {value:.3f}")


if __name__ == "__main__":
    main()
