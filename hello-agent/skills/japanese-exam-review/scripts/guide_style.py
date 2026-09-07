# -*- coding: utf-8 -*-
"""guide_style.py — 命令式排版引擎（移植自 software_engineering_study_guide_v2 的 SEPDF）。

为什么是命令式：内容由 Claude 按阅读顺序直接调用这些方法"画"进 PDF
（像 v2 的 generate_guide_fpdf.py 一样），而不是把内容塞进 JSON 再交给
通用渲染器。字体只用 SimSun 一个，配色只用 3 组强调色——版式纪律来自
"方法就这么几个、颜色就这么几种"，而不是几百行规则。

Windows SimSun 缺 U+30FB(・ 片假名中黑点) 字形，但内容里大量出现
（如 送信元・送信先）。所有文本入口统一做 ・→· (U+30FB→U+00B7) 归一化，
这样就能单字体跑通，与 v2 的做法一致。
"""
import os
import struct
from fpdf import FPDF

FONT_NAME = "CJK"

# ---------- 配色（与 v2 完全一致，勿改） ----------
NAVY = (26, 58, 92)          # 章标题 17pt
NAVY2 = (40, 60, 90)         # h2 小节标题 12pt
NAVY3 = (40, 50, 70)         # body_jp 日文关键句
RED = (200, 50, 50)          # 考试红字【試験】+ 章红字副标题 + ▲图注
RED2 = (180, 50, 50)         # ▲ 图注
DARKBROWN = (60, 30, 30)     # body_cn 中文正文
GRAY_BODY = (50, 50, 50)     # body 中性正文
GRAY2 = (70, 70, 70)         # h3
GRAY_SUB = (100, 100, 100)   # 图的灰字细说明
GRAY_LINE = (180, 180, 180)  # 分隔线
GRAY_LINE2 = (200, 200, 200) # hr
GRAY_BORDER = (210, 210, 210)  # 表格边框
HEADER_BG = (40, 50, 70)     # 表头深藏青底
ZEBRA_BG = (240, 244, 248)   # 表格隔行浅蓝灰
FOOTER_GRAY = (150, 150, 150)


def norm(s):
    """文本归一化：把 SimSun 没有的 ・(U+30FB) 换成有的 ·(U+00B7)。"""
    return str(s).replace("・", "·")


class SEPDF(FPDF):
    """A4 纵向，单 SimSun，自动分页(底边距 18mm)。"""

    def __init__(self, font_file=None):
        super().__init__("P", "mm", "A4")
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fonts = os.path.join(base, "fonts")
        candidates = [font_file] if isinstance(font_file, str) else (
            [os.path.join(fonts, "simsun_extracted.ttf"),
             os.path.join(fonts, "simsun.ttc")] if font_file is None else list(font_file))
        for c in candidates:
            if c and os.path.exists(c):
                try:
                    self.add_font(FONT_NAME, "", c)
                    self.set_auto_page_break(True, 18)
                    return
                except Exception as e:
                    print(f"字体注册失败 {c}: {e}")
        raise RuntimeError("无法注册 SimSun 字体，请检查 fonts/ 目录")

    # ---------------- 封面 ----------------
    def title_page(self, jp, cn, en, sub, tagline, meta_rows):
        self.add_page()
        self.ln(50)
        self.set_font(FONT_NAME, "", 24)
        self.set_text_color(0, 0, 0)
        self.cell(0, 12, norm(jp), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font(FONT_NAME, "", 20)
        self.cell(0, 10, norm(cn), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font(FONT_NAME, "", 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, norm(en), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_draw_color(*GRAY_LINE)
        self.line(30, self.get_y(), self.w - 30, self.get_y())
        self.ln(8)
        self.set_font(FONT_NAME, "", 13)
        self.set_text_color(30, 50, 80)
        self.cell(0, 8, norm(sub), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.set_font(FONT_NAME, "", 10)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, norm(tagline), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.line(30, self.get_y(), self.w - 30, self.get_y())
        self.ln(8)
        self.set_font(FONT_NAME, "", 9)
        self.set_text_color(0, 0, 0)
        for label, value in meta_rows:
            self.set_fill_color(*HEADER_BG)
            self.set_text_color(255, 255, 255)
            self.set_font(FONT_NAME, "", 9)
            self.cell(32, 8, " " + norm(label), fill=True, new_x="RIGHT", new_y="LAST")
            self.set_fill_color(*ZEBRA_BG)
            self.set_text_color(0, 0, 0)
            self.cell(self.w - 62, 8, norm(value), fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

    # ---------------- 章 ----------------
    def chapter_title(self, num, jp, cn, stars):
        self.add_page()
        self.set_font(FONT_NAME, "", 17)
        self.set_text_color(*NAVY)
        self.cell(0, 9, f"第{num}回  {norm(jp)}", new_x="LMARGIN", new_y="NEXT")
        self.set_font(FONT_NAME, "", 10)
        self.set_text_color(*RED)
        self.cell(0, 6, f"{norm(cn)}   試験重要度: {stars}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*GRAY_LINE)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)

    def h2(self, text):
        self.set_font(FONT_NAME, "", 12)
        self.set_text_color(*NAVY2)
        self.cell(0, 7, norm(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h3(self, text):
        self.set_font(FONT_NAME, "", 10)
        self.set_text_color(*GRAY2)
        self.cell(0, 6, norm(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text):
        """中性正文（默认底色文字）。"""
        self.set_font(FONT_NAME, "", 8.5)
        self.set_text_color(*GRAY_BODY)
        self.multi_cell(0, 5.2, norm(text), align="L")
        self.ln(0.5)

    def body_cn(self, text):
        """中文正文（深棕）。"""
        self.set_font(FONT_NAME, "", 8.5)
        self.set_text_color(*DARKBROWN)
        self.multi_cell(0, 5.2, norm(text), align="L")
        self.ln(0.5)

    def body_jp(self, text):
        """日文关键句（藏青，内容行内自带【中】翻译则直接写在 text 里）。"""
        self.set_font(FONT_NAME, "", 8.5)
        self.set_text_color(*NAVY3)
        self.multi_cell(0, 5.2, norm(text), align="L")
        self.ln(0.5)

    def exam(self, text):
        """考试红字提示，自动加【試験】前缀。"""
        self.set_font(FONT_NAME, "", 8.5)
        self.set_text_color(*RED)
        self.multi_cell(0, 5.2, norm(f"【試験】{text}"), align="L")
        self.ln(0.5)

    # ---------------- 表格 ----------------
    def make_table(self, headers, rows, col_widths, header_bg=HEADER_BG):
        available = self.w - self.l_margin - self.r_margin
        if sum(col_widths) != available:
            col_widths = [w * available / sum(col_widths) for w in col_widths]

        x0 = self.l_margin

        def draw_header():
            self.set_fill_color(*header_bg)
            self.set_text_color(255, 255, 255)
            self.set_font(FONT_NAME, "", 7.5)
            for i, (h, w) in enumerate(zip(headers, col_widths)):
                self.set_xy(x0 + sum(col_widths[:i]), self.get_y())
                self.cell(w, 7, norm(h), border=0, fill=True, align="C")
            self.ln(7)

        draw_header()
        for ri, row in enumerate(rows):
            self.set_fill_color(ZEBRA_BG if ri % 2 else (255, 255, 255))
            self.set_text_color(40, 40, 40)
            self.set_font(FONT_NAME, "", 7)

            max_lines = 1
            for cell_text, w in zip(row, col_widths):
                lines = self.multi_cell(w - 2, 4.5, norm(cell_text),
                                        dry_run=True, output="LINES")
                if lines:
                    max_lines = max(max_lines, len(lines))
            row_h = max(5, max_lines * 4.5 + 2)

            if self.get_y() + row_h > self.h - self.b_margin:
                self.add_page()
                draw_header()
                self.set_fill_color(ZEBRA_BG if ri % 2 else (255, 255, 255))

            y_start = self.get_y()
            for ci, (cell_text, w) in enumerate(zip(row, col_widths)):
                self.set_xy(x0 + sum(col_widths[:ci]), y_start)
                self.set_font(FONT_NAME, "", 7)
                self.set_text_color(40, 40, 40)
                self.multi_cell(w - 2, 4.5, norm(cell_text), align="L")
                self.set_draw_color(*GRAY_BORDER)
                self.rect(x0 + sum(col_widths[:ci]), y_start, w, row_h)
            self.set_xy(x0, y_start + row_h)
        self.ln(3)

    # ---------------- 分隔线 / 图 ----------------
    def hr(self):
        self.set_draw_color(*GRAY_LINE2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    @staticmethod
    def _png_size(path):
        """读 PNG 文件头拿到像素宽高（IHDR）。非 PNG 返回 None。"""
        try:
            with open(path, "rb") as f:
                head = f.read(24)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return w, h
        except OSError:
            pass
        return None

    def add_figure(self, img_path, caption_cn="", caption_detail="", w=150):
        """嵌一张讲义截图：先算好高度，空间不够就自动换页，然后画图和说明。
        caption_cn = 红色 ▲ 一行主图注；caption_detail = 灰字细说明(可多行)。"""
        if not os.path.exists(img_path):
            print(f"图不存在，跳过: {img_path}")
            return False
        sz = self._png_size(img_path)
        h = w * sz[1] / sz[0] if sz else w * 0.6
        if self.get_y() + h + 26 > self.h - self.b_margin:
            self.add_page()
        self.ln(2)
        self.image(img_path, x=self.get_x(), w=w, h=h)
        self.ln(2)
        if caption_cn:
            self.set_font(FONT_NAME, "", 8)
            self.set_text_color(*RED2)
            self.multi_cell(0, 4.6, norm("▲ " + caption_cn), align="L")
            self.ln(0.5)
        if caption_detail:
            self.set_font(FONT_NAME, "", 7)
            self.set_text_color(*GRAY_SUB)
            self.multi_cell(0, 4, norm(caption_detail), align="L")
            self.ln(0.5)
        self.ln(2)
        return True

    # ---------------- 页脚 ----------------
    def footer(self):
        self.set_y(-15)
        self.set_font(FONT_NAME, "", 7)
        self.set_text_color(*FOOTER_GRAY)
        self.cell(0, 8, f"- {self.page_no()} -", align="C")
