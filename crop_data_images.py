from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PAGE_RE = re.compile(r"^(?P<prefix>.+?)_页面_(?P<page>\d+)$")
TRAILING_PAGE_RE = re.compile(r"^(?P<prefix>.+?)[_.-](?P<page>\d+)$")
AUTHOR_MARKER = ".常盘大定.关野贞著.法蔵馆"


@dataclass(frozen=True)
class CropBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class SmallDetection:
    box: CropBox
    area: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop printed photo blocks from scanned book plates."
    )
    parser.add_argument("--input", default="data", type=Path)
    parser.add_argument("--output", default="output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--max-dim",
        default=1800,
        type=int,
        help="Maximum dimension for detection pass; crops are still saved from original pixels.",
    )
    parser.add_argument(
        "--safety-pixels",
        default=4,
        type=int,
        help="Tiny outward expansion to avoid cutting a printed-photo edge.",
    )
    return parser.parse_args()


def iter_images(input_root: Path) -> list[Path]:
    return sorted(
        p
        for p in input_root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def output_stem(path: Path) -> str:
    match = PAGE_RE.match(path.stem) or TRAILING_PAGE_RE.match(path.stem)
    if not match:
        raise ValueError(f"Cannot parse page number from filename: {path.name}")

    prefix = match.group("prefix")
    page = match.group("page")
    book_name = prefix.split(AUTHOR_MARKER, 1)[0]
    return f"{book_name}.{page}"


def resize_for_detection(rgb: np.ndarray, max_dim: int) -> tuple[np.ndarray, float]:
    height, width = rgb.shape[:2]
    scale = min(1.0, max_dim / max(width, height))
    if scale == 1.0:
        return rgb.copy(), scale

    small = cv2.resize(
        rgb,
        (round(width * scale), round(height * scale)),
        interpolation=cv2.INTER_AREA,
    )
    return small, scale


def estimate_paper_lab(lab: np.ndarray) -> np.ndarray:
    height, width = lab.shape[:2]
    margin_y = max(8, round(height * 0.055))
    margin_x = max(8, round(width * 0.055))

    border = np.concatenate(
        [
            lab[:margin_y, :, :].reshape(-1, 3),
            lab[-margin_y:, :, :].reshape(-1, 3),
            lab[:, :margin_x, :].reshape(-1, 3),
            lab[:, -margin_x:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    light_cut = np.percentile(border[:, 0], 55)
    paperish = border[border[:, 0] >= light_cut]
    if paperish.size == 0:
        paperish = border
    return np.median(paperish, axis=0)


def photo_score_map(small_rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(small_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    gray = cv2.cvtColor(small_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    paper_lab = estimate_paper_lab(lab)

    color_delta = np.linalg.norm(lab - paper_lab, axis=2)
    paper_l = float(paper_lab[0])
    paper_gray = np.percentile(gray, 82)

    border = max(4, round(min(small_rgb.shape[:2]) * 0.055))
    border_delta = np.concatenate(
        [
            color_delta[:border, :].reshape(-1),
            color_delta[-border:, :].reshape(-1),
            color_delta[:, :border].reshape(-1),
            color_delta[:, -border:].reshape(-1),
        ]
    )
    paper_delta = np.percentile(border_delta, 70)

    dark_delta = np.maximum(0.0, np.maximum(paper_l, paper_gray) - gray)
    dark_score = np.clip(dark_delta / 58.0, 0.0, 1.0)
    color_score = np.clip((color_delta - paper_delta) / 36.0, 0.0, 1.0)
    score = np.maximum(dark_score, color_score * 0.8)

    scan_border = max(4, round(min(small_rgb.shape[:2]) * 0.01))
    score[:scan_border, :] = 0
    score[-scan_border:, :] = 0
    score[:, :scan_border] = 0
    score[:, -scan_border:] = 0
    return score.astype(np.float32)


def rough_photo_boxes(small_rgb: np.ndarray) -> list[SmallDetection]:
    gray = cv2.cvtColor(small_rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    border_for_paper = max(12, round(min(width, height) * 0.055))
    edge_pixels = np.concatenate(
        [
            gray[:border_for_paper, :].reshape(-1),
            gray[-border_for_paper:, :].reshape(-1),
            gray[:, :border_for_paper].reshape(-1),
            gray[:, -border_for_paper:].reshape(-1),
        ]
    )
    paper_gray = np.percentile(edge_pixels, 75)
    threshold = min(np.percentile(gray, 58), paper_gray - 18)
    binary = (gray < threshold).astype(np.uint8) * 255

    border = max(12, round(min(width, height) * 0.015))
    binary[:border, :] = 0
    binary[-border:, :] = 0
    binary[:, :border] = 0
    binary[:, -border:] = 0

    labels, stats = cv2.connectedComponentsWithStats(binary, 8)[1:3]
    _ = labels

    min_area = width * height * 0.025
    min_width = width * 0.18
    min_height = height * 0.18
    boxes: list[CropBox] = []
    for label in range(1, stats.shape[0]):
        x, y, box_width, box_height, area = stats[label]
        if area < min_area:
            continue
        if box_width < min_width or box_height < min_height:
            continue
        boxes.append(CropBox(int(x), int(y), int(x + box_width), int(y + box_height)))

    detections = [SmallDetection(box, box.area) for box in boxes]
    return detections


def contiguous_edge(
    profile: np.ndarray, start_low: int, start_high: int, low: int, high: int
) -> tuple[int, int]:
    outside = np.concatenate([profile[low:start_low], profile[start_high:high]])
    inside = profile[start_low:start_high]
    if inside.size == 0:
        return start_low, start_high

    baseline = float(np.percentile(outside, 45)) if outside.size else float(np.min(profile))
    inside_level = float(np.percentile(inside, 52))
    threshold = baseline + max(0.035, (inside_level - baseline) * 0.22)

    run = 0
    top = start_low
    for idx in range(start_low - 1, low - 1, -1):
        if profile[idx] >= threshold:
            top = idx
            run = 0
        else:
            run += 1
            if run >= 3:
                break

    run = 0
    bottom = start_high
    for idx in range(start_high, high):
        if profile[idx] >= threshold:
            bottom = idx + 1
            run = 0
        else:
            run += 1
            if run >= 3:
                break

    return top, bottom


def refine_box(score: np.ndarray, rough: CropBox) -> CropBox:
    height, width = score.shape
    pad_x = max(12, round(width * 0.055))
    pad_y = max(12, round(height * 0.055))
    search = CropBox(
        max(0, rough.x1 - pad_x),
        max(0, rough.y1 - pad_y),
        min(width, rough.x2 + pad_x),
        min(height, rough.y2 + pad_y),
    )

    low_mask = (score > 0.12).astype(np.float32)
    smoothed_score = cv2.GaussianBlur(score, (9, 9), 0)

    x_span = slice(max(search.x1, rough.x1), min(search.x2, rough.x2))
    y_profile = (
        low_mask[search.y1 : search.y2, x_span].mean(axis=1) * 0.60
        + smoothed_score[search.y1 : search.y2, x_span].mean(axis=1) * 0.40
    )
    y_profile = cv2.GaussianBlur(y_profile.reshape(-1, 1), (1, 9), 0).ravel()
    y1, y2 = contiguous_edge(
        y_profile,
        rough.y1 - search.y1,
        rough.y2 - search.y1,
        0,
        search.y2 - search.y1,
    )
    y1 += search.y1
    y2 += search.y1

    y_span = slice(max(search.y1, y1), min(search.y2, y2))
    x_profile = (
        low_mask[y_span, search.x1 : search.x2].mean(axis=0) * 0.60
        + smoothed_score[y_span, search.x1 : search.x2].mean(axis=0) * 0.40
    )
    x_profile = cv2.GaussianBlur(x_profile.reshape(1, -1), (9, 1), 0).ravel()
    x1, x2 = contiguous_edge(
        x_profile,
        rough.x1 - search.x1,
        rough.x2 - search.x1,
        0,
        search.x2 - search.x1,
    )
    x1 += search.x1
    x2 += search.x1

    return CropBox(x1, y1, x2, y2)


def sort_reading_order(boxes: list[CropBox]) -> list[CropBox]:
    if len(boxes) <= 1:
        return boxes

    centers_x = np.array([(box.x1 + box.x2) / 2 for box in boxes])
    centers_y = np.array([(box.y1 + box.y2) / 2 for box in boxes])
    spread_x = centers_x.max() - centers_x.min()
    spread_y = centers_y.max() - centers_y.min()

    if spread_x >= spread_y:
        return sorted(boxes, key=lambda box: (box.x1, box.y1))
    return sorted(boxes, key=lambda box: (box.y1, box.x1))


def detect_photo_boxes(rgb: np.ndarray, max_dim: int, safety_pixels: int) -> list[CropBox]:
    small_rgb, scale = resize_for_detection(rgb, max_dim)
    score = photo_score_map(small_rgb)
    detections = rough_photo_boxes(small_rgb)
    if not detections:
        return []

    refined_small = [refine_box(score, detection.box) for detection in detections]

    height, width = rgb.shape[:2]
    boxes: list[CropBox] = []
    for box in refined_small:
        x1 = max(0, int(np.floor(box.x1 / scale)) - safety_pixels)
        y1 = max(0, int(np.floor(box.y1 / scale)) - safety_pixels)
        x2 = min(width, int(np.ceil(box.x2 / scale)) + safety_pixels)
        y2 = min(height, int(np.ceil(box.y2 / scale)) + safety_pixels)
        candidate = CropBox(x1, y1, x2, y2)
        if candidate.area >= width * height * 0.025:
            boxes.append(candidate)

    return sort_reading_order(boxes)


def make_output_path(output_root: Path, relative_parent: Path, stem: str, index: int, count: int) -> Path:
    suffix = "" if count == 1 else chr(ord("a") + index - 1)
    return output_root / relative_parent / f"{stem}{suffix}.jpg"


def process_image(
    path: Path,
    input_root: Path,
    output_root: Path,
    dry_run: bool,
    overwrite: bool,
    max_dim: int,
    safety_pixels: int,
) -> tuple[int, list[CropBox]]:
    with Image.open(path) as image:
        image = image.convert("RGB")
        rgb = np.array(image)
        boxes = detect_photo_boxes(rgb, max_dim, safety_pixels)

        relative_parent = path.parent.relative_to(input_root)
        stem = output_stem(path)
        for idx, box in enumerate(boxes, start=1):
            out_path = make_output_path(output_root, relative_parent, stem, idx, len(boxes))
            if dry_run:
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.exists() and not overwrite:
                raise FileExistsError(f"Output already exists: {out_path}")
            crop = image.crop((box.x1, box.y1, box.x2, box.y2))
            crop.save(out_path, format="JPEG", quality=95, subsampling=0)

    return len(boxes), boxes


def main() -> None:
    args = parse_args()
    input_root = args.input.resolve()
    output_root = args.output.resolve()

    images = iter_images(input_root)
    if not images:
        raise SystemExit(f"No images found under {input_root}")

    total = 0
    anomalies: list[str] = []
    for path in images:
        count, boxes = process_image(
            path,
            input_root,
            output_root,
            args.dry_run,
            args.overwrite,
            args.max_dim,
            args.safety_pixels,
        )
        total += count
        if count not in {1, 2}:
            anomalies.append(f"{path}: detected {count} photo blocks")
        box_text = ", ".join(
            f"({box.x1},{box.y1})-({box.x2},{box.y2}) {box.width}x{box.height}"
            for box in boxes
        )
        print(f"{path.relative_to(input_root)} -> {count}: {box_text}")

    print(f"Processed {len(images)} source images; detected {total} photo blocks.")
    if anomalies:
        print("Anomalies:")
        for anomaly in anomalies:
            print(f"  {anomaly}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
