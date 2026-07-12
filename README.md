# yungang-crop

从扫描书籍图版中自动检测并裁剪印刷照片区域。

本仓库只保存裁剪脚本、依赖清单和项目说明。原始扫描图、压缩包和生成后的裁剪结果都属于数据文件，体积较大，因此不会提交到 Git。

## 目录结构

请把数据保存在本地目录中：

```text
data/      # 输入扫描图，不提交
output/    # 生成的裁剪 JPEG，不提交
```

脚本默认从 `data/` 读取图片，并将裁剪后的 JPEG 写入 `output/`。

## 安装

建议使用 Python 3.12 或较新的 Python 3 版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 使用方法

只预览检测结果，不写入输出文件：

```powershell
python crop_data_images.py --dry-run
```

执行裁剪，并将 JPEG 结果写入 `output/`：

```powershell
python crop_data_images.py
```

指定输入和输出目录：

```powershell
python crop_data_images.py --input data --output output
```

允许覆盖已经存在的输出文件：

```powershell
python crop_data_images.py --overwrite
```

## 参数说明

- `--input`：源图片所在目录，默认值为 `data`。
- `--output`：裁剪结果输出目录，默认值为 `output`。
- `--dry-run`：只检测并打印裁剪框，不写入文件。
- `--overwrite`：允许覆盖已经存在的输出文件。
- `--max-dim`：检测阶段使用的最大图像边长；最终裁剪仍会使用原始像素，默认值为 `1800`。
- `--safety-pixels`：裁剪框向外扩展的安全像素数，用于避免切到印刷照片边缘，默认值为 `4`。

## 数据管理

`.gitignore` 已排除 `data/`、`output/`、Python 缓存、虚拟环境和本地环境变量文件。请将源扫描图、zip 压缩包和生成图像保留在本地，不要提交到 GitHub。
