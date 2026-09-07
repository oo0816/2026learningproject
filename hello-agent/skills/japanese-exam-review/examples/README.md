# Examples

## B 通路示例输入

`content_b_example.json` — 通路 B（内容 JSON）的完整示例：计算机网络第 02 回复习文档，含封面 / 目次 / 两章（回線交換 vs パケット交換 + Kleinrock）/ 讲义原图 / 术语表 / 红字考点。

再生成 PDF（写入 `output/`）：

```bash
python scripts/path_b_render.py examples/content_b_example.json -o output/sample_b.pdf
```

## A 通路示例脚本

`../scripts/build_sample_a.py` — 同一内容的**直写版**（通路 A），直接调用 `guide_style` 排版。

`output/sample_a.pdf` 与 `output/sample_b.pdf` 已逐页核对完全一致——证明两条通路共用同一套版式。

> 新产出应以这两个样张为"同味"基准；版式元件与纪律见 `../SKILL.md` → 统一版式。
