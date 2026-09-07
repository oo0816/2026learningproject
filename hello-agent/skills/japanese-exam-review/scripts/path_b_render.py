# -*- coding: utf-8 -*-
"""path_b_render.py — 通路B 薄渲染：极简内容 JSON → PDF（复用 guide_style 引擎）。

设计原则：B 不是另一套版式，只是把 A 直写时"按顺序调方法"这件事序列化成 JSON，
再原样映射回 guide_style 的方法。所以 A 直写（build_*.py）和 B（content JSON）
产出的 PDF 共用同一套版式——颜色、字号、表格、图注、红字考点全部一致。

内容 JSON 允许的块（= guide_style 允许的方法，多一个都不行，防止另起风格）：
  para   段落     {type, kind:"cn"|"jp"|"note", text}   → body_cn/body_jp/body
  heading 小节标题  {type, level:2|3, text}               → h2/h3
  table   表格/术语表 {type, headers[], col_widths?, rows[[]]} → make_table
  figure  讲义原图  {type, file, caption_cn?, caption_detail?, w?} → add_figure
  exam    考试红字  {type, text}                          → exam（自动加【試験】前缀）
顶层：
  cover:  {jp, cn, en, sub, tagline, meta:[[标签,值],...]}   → 封面（可省）
  toc:    [[#, 主题, 重要度],...]                            → 目次页（可省）
  sections:[{num, jp, cn, stars, blocks[]}]                   → 每节一页 chapter_title
"""
import argparse
import json
import os
import sys
from pathlib import Path

from guide_style import SEPDF, HEADER_BG, NAVY, RED

BASE = Path(__file__).resolve().parent.parent          # skill 根
IMG_DIR = BASE / "output" / "images"                   # 解析出的讲义图

TOC_HEADERS = ["#", "テーマ / 主题", "重要度"]
TOC_WIDTHS = [14, 141, 25]


def _err(sec, block, msg):
    raise ValueError(f"通路B schema 错误 [{sec}]{block}: {msg}")


def render_cover(pdf, cover):
    pdf.title_page(
        jp=cover.get("jp", ""),
        cn=cover.get("cn", ""),
        en=cover.get("en", ""),
        sub=cover.get("sub", ""),
        tagline=cover.get("tagline", ""),
        meta_rows=cover.get("meta", []),
    )


def render_toc(pdf, toc, toc_title="目次 / 目录"):
    pdf.add_page()
    pdf.set_font("CJK", "", 15)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 9, toc_title, new_x="LMARGIN", new_y="NEXT")
    pdf.hr()
    rows = [[str(a), str(b), str(c)] for a, b, c in toc]
    pdf.make_table(TOC_HEADERS, rows, TOC_WIDTHS)


def render_block(pdf, sec_name, b):
    t = b.get("type")
    if t == "para":
        kind = b.get("kind", "cn")
        method = {"cn": "body_cn", "jp": "body_jp", "note": "body"}.get(kind)
        if method is None:
            _err(sec_name, b, "para.kind 只允许 cn / jp / note")
        getattr(pdf, method)(b.get("text", ""))
    elif t == "heading":
        level = b.get("level", 2)
        getattr(pdf, "h3" if level >= 3 else "h2")(b.get("text", ""))
    elif t == "table":
        rows = b.get("rows", [])
        if not rows or not rows[0]:
            _err(sec_name, b, "table.rows 不能为空")
        pdf.make_table(b.get("headers", []), rows, b.get("col_widths"))
    elif t == "figure":
        f = b.get("file", "")
        if not f:
            _err(sec_name, b, "figure.file 必填（相对 output/images/ 的文件名）")
        pdf.add_figure(
            str(IMG_DIR / f),
            caption_cn=b.get("caption_cn", ""),
            caption_detail=b.get("caption_detail", ""),
            w=b.get("w", 150),
        )
    elif t == "exam":
        pdf.exam(b.get("text", ""))
    else:
        _err(sec_name, b, f"未知块类型 {t!r}（只允许 para/heading/table/figure/exam）")


def render(doc, out, img_dir=None):
    """content JSON → PDF。img_dir 可覆盖 output/images（测试用）。"""
    global IMG_DIR
    if img_dir is not None:
        IMG_DIR = Path(img_dir)

    pdf = SEPDF()
    pdf.set_margin(15)

    if doc.get("cover"):
        render_cover(pdf, doc["cover"])

    toc = doc.get("toc")
    if toc:
        render_toc(pdf, toc, doc.get("toc_title", "目次 / 目录"))

    for sec in doc.get("sections", []):
        pdf.chapter_title(
            sec.get("num", ""),
            sec.get("jp", ""),
            sec.get("cn", ""),
            sec.get("stars", ""),
        )
        for b in sec.get("blocks", []):
            render_block(pdf, sec.get("jp", sec.get("num", "?")), b)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


def main():
    ap = argparse.ArgumentParser(description="通路B：内容 JSON → 复习 PDF（guide_style 版式）")
    ap.add_argument("input", help="content JSON 路径")
    ap.add_argument("-o", "--output", default="output/review.pdf", help="输出 PDF")
    args = ap.parse_args()
    if not Path(args.input).exists():
        print(f"Error: 找不到 {args.input}")
        sys.exit(1)
    with open(args.input, "r", encoding="utf-8") as f:
        doc = json.load(f)
    result = render(doc, args.output)
    print(f"OK 通路B 生成 {result}")


if __name__ == "__main__":
    main()
