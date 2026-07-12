# yungang-crop

Crop printed photo blocks from scanned book plate images.

This repository contains the cropping script and project documentation only. Raw scans and generated cropped images are intentionally kept out of Git because they are large data artifacts.

## Layout

Keep data in local-only folders:

```text
data/      # input scans, not committed
output/    # generated cropped JPEGs, not committed
```

By default, the script reads images from `data/` and writes cropped JPEG files to `output/`.

## Install

Use Python 3.12 or a recent Python 3 release.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Usage

Preview detections without writing output files:

```powershell
python crop_data_images.py --dry-run
```

Run the cropper and write JPEG crops under `output/`:

```powershell
python crop_data_images.py
```

Run with explicit folders:

```powershell
python crop_data_images.py --input data --output output
```

Overwrite existing output files:

```powershell
python crop_data_images.py --overwrite
```

## Arguments

- `--input`: input folder containing source images. Defaults to `data`.
- `--output`: output folder for cropped JPEG files. Defaults to `output`.
- `--dry-run`: detect and print crop boxes without writing files.
- `--overwrite`: allow existing output files to be replaced.
- `--max-dim`: maximum image dimension used during detection. Crops are still saved from original pixels. Defaults to `1800`.
- `--safety-pixels`: outward crop expansion in pixels to avoid cutting printed-photo edges. Defaults to `4`.

## Data Policy

The repository ignores `data/`, `output/`, Python caches, virtual environments, and local environment files. Keep source scans, zip archives, and generated images outside Git.
