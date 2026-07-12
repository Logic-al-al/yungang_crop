# yungang-crop

从扫描书籍图版中自动检测并裁剪印刷照片区域，并为裁剪后的照片生成 xlsx 信息表。

现在可以完成自动crop裁切以及命名、存储，自动填写表格的书籍名称和编号，但由于日语、繁体中文、竖排字等情况难以处理，目前使用较轻的识别依赖不能有效识别填写注释。


## 目录结构


```text
data/       # 输入扫描图，按书籍或批次分文件夹存放
output/     # 裁剪后的 JPEG、xlsx、注释复核文件
```


## 安装

建议使用 Python 3.12 或较新的 Python 3 版本。

```powershell
python -m pip install -r requirements.txt
```

依赖里包含 `rapidocr-onnxruntime`，用于自动识别图版页上的注释。如果只想生成空注释表，也可以在生成 xlsx 时加 `--no-ocr`。

## 新书处理流程

1. 准备扫描图

   把新书图片放到 `data/<书籍或批次文件夹>/` 下。生成 xlsx 时，脚本会用这个文件夹名匹配裁剪图和原始页，所以同一本书的输入、输出会保持同一个子目录名。

   文件名建议使用：

   ```text
   书名_页面_001.png
   书名_页面_002.png
   书名_页面_003.png
   ```

   页码最好是 3 位数字，因为后续 xlsx 脚本会识别 `001`、`002a`、`002b` 这样的照片编号。

2. 先预览裁剪结果

   ```powershell
   python crop_data_images.py --input data --output output --dry-run
   ```

   这一步只打印每页检测到的照片框，不写入文件。正常情况下，每页应检测到 1 或 2 个照片块。若出现 `Anomalies`，说明某些页检测数量不是 1 或 2，需要重点检查原图或调整参数。

3. 执行裁剪

   ```powershell
   python crop_data_images.py --input data --output output
   ```

   裁剪结果会写入 `output/<原输入子目录>/`。如果一页只有一张照片，文件名类似 `书名.001.jpg`；如果一页有两张照片，文件名类似 `书名.001a.jpg`、`书名.001b.jpg`。

   如果输出文件已经存在，需要覆盖时使用：

   ```powershell
   python crop_data_images.py --input data --output output --overwrite
   ```

4. 生成 xlsx 信息表

   ```powershell
   python build_photo_metadata.py --data data --output output
   ```

   脚本会扫描 `output/<文件夹>/` 下的裁剪照片，并回到 `data/<同名文件夹>/` 找对应的原始页，生成：

   ```text
   output/<文件夹>/云冈老照片信息收集表_<文件夹>.xlsx
   output/annotation_review/annotation_review.csv
   output/annotation_review/caption_crops/<文件夹>/
   ```

   xlsx 表头为：`序号`、`书籍名称`、`照片编号`、`图片注释`。其中“图片注释”会尽量从原始页 OCR 自动解析；识别不稳定时，请以复核文件和原图为准人工修正。

5. 只生成表格结构，不自动 OCR 注释

   如果新书注释版式差异较大，或者希望人工填写注释，可以跳过 OCR：

   ```powershell
   python build_photo_metadata.py --data data --output output --no-ocr
   ```

   这样 xlsx 仍会包含所有照片记录，但“图片注释”列为空。



## 文件命名要求

- crop_data_images.py文件中的AUTHOR_MARKER修改为新的作者和出版社 
- 原始扫描图需要放在 `data/<文件夹>/` 下。
- 生成 xlsx 时，原始扫描图文件名必须包含 `_页面_页码`，例如 `某书名_页面_013.png`。
- 裁剪图文件名需要是 `书名.013.jpg`、`书名.013a.jpg`、`书名.013b.jpg` 这种形式。
- `data/<文件夹名>/` 和 `output/<文件夹名>/` 必须对应，否则 xlsx 脚本找不到原始页。
- 当前 xlsx 脚本只在原始数据中查找 `.png` 页面；如果新书是 `.jpg` 或 `.tif` 原始页，需要先转成 `.png`，或修改脚本支持对应格式。

## 常用参数

### `crop_data_images.py`

- `--input`：源图片目录，默认 `data`。
- `--output`：裁剪结果目录，默认 `output`。
- `--dry-run`：只检测并打印裁剪框，不写入文件。
- `--overwrite`：允许覆盖已经存在的裁剪图。
- `--max-dim`：检测阶段使用的最大图像边长；最终裁剪仍使用原始像素，默认 `1800`。
- `--safety-pixels`：裁剪框向外扩展的安全像素数，默认 `4`。

### `build_photo_metadata.py`

- `--data`：原始扫描图目录，默认 `data`。
- `--output`：裁剪图和 xlsx 输出目录，默认 `output`。
- `--review-dir`：注释复核材料输出目录，默认 `output/annotation_review`。
- `--dry-run`：运行检测和 OCR 流程，但不写入 xlsx、csv、注释裁片。
- `--no-ocr`：不运行 OCR，xlsx 的“图片注释”列留空。
- `--overwrite`：允许覆盖已经存在的 xlsx。
- `--pages`：只处理指定页码，例如 `--pages 013 014`。

## 建议检查项

- 裁剪后先快速浏览 `output/<文件夹>/`，确认照片没有漏裁、误裁或切边。
- 如果裁剪脚本报告 `Anomalies`，优先检查对应页。
- 生成 xlsx 后，查看 `output/annotation_review/annotation_review.csv` 和 `caption_crops`，复核 OCR 注释是否可信。
- 新书版式差异较大时，先用少量页面测试：`--dry-run` 或 `--pages` 会省很多时间。
