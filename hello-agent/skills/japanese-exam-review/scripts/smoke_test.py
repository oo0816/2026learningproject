# -*- coding: utf-8 -*-
"""smoke_test.py — japanese-exam-review 快速冒烟测试（免费、秒级、可复跑）。

这个 skill 有两类"验证"，别混：
  · 本脚本（快速冒烟）  = 验证 skill 的【确定性部件】还能不能用：
      依赖、字体、脚本语法、解析产物、内容 JSON schema、覆盖率、A/B 两通路渲染。
    不花 token、不请 LLM，任何时刻跑一遍，几秒出结果。
  · test-prompts.json   = 3 个【agent 端到端】场景（复习 / 考点回忆版 / 无材料防幻觉），
      要真子 agent 带 SKILL 跑才算数（darwin full_test 那类），本脚本不碰。

用法（在 skill 根目录）：
    python scripts/smoke_test.py
    python scripts/smoke_test.py examples/content_b_example.json --cov-min 85
    python scripts/smoke_test.py <你新写的 content.json>        # 换成真实内容做回归

退出码：0 = 全部通过；1 = 有 FAIL（WARN/SKIP 不算失败）。
退出码 2 = 参数错误。
"""
import argparse
import importlib
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent            # scripts/
ROOT = HERE.parent                                # skill 根
OUT_DIR = ROOT / "output"

REQ_DEPS = [("fitz", "PyMuPDF"), ("fpdf", "fpdf2"), ("pptx", "python-pptx"), ("PIL", "Pillow")]
ALLOWED_BLOCKS = {"para", "heading", "table", "figure", "exam"}
ALLOWED_TOP = {"cover", "toc", "sections", "toc_title"}
ALLOWED_KIND = {"cn", "jp", "note"}

_MARKS = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": " [WARN]", "SKIP": " [SKIP]"}
_results = []  # (name, status, detail)


def report(name, ok=True, detail="", status=None):
    """记录并打印一行结果。status 可显式指定 PASS/FAIL/WARN/SKIP，否则由 ok 推断。"""
    if status is None:
        status = "PASS" if ok else "FAIL"
    _results.append((name, status, detail))
    print(f"{_MARKS[status]} {name}")
    for line in str(detail).strip().splitlines():
        if line:
            print(f"        {line}")


def print_header(script_args):
    print("=" * 64)
    print("japanese-exam-review 快速冒烟测试")
    print(f"skill 根目录 : {ROOT}")
    print(f"python       : {sys.version.split()[0]}  ({sys.executable})")
    print("=" * 64)
    print(f"测试对象     : {script_args.content}（覆盖率下限 {script_args.cov_min}%）")
    print()


def step_deps():
    """[1] 依赖：四个三方库能否 import（requirements.txt 全部项）。"""
    missing = []
    for mod, pip_name in REQ_DEPS:
        try:
            importlib.import_module(mod)
        except Exception as e:
            missing.append(f"{pip_name}（{mod}）: {e}")
    if missing:
        report("1. Python 依赖可导入", False,
               "缺：\n" + "\n".join("  - " + m for m in missing) +
               "\n安装：python -m pip install -r requirements.txt")
    else:
        report("1. Python 依赖可导入", True, "fitz / fpdf / pptx / PIL 全部就绪")


def step_fonts():
    """[2] 字体：引擎依赖 fonts/ 里的 SimSun（渲染 PDF 的必需前提）。"""
    fonts_dir = ROOT / "fonts"
    have_ttf = (fonts_dir / "simsun_extracted.ttf").exists()
    have_ttc = (fonts_dir / "simsun.ttc").exists()
    if have_ttf or have_ttc:
        detail = "simsun_extracted.ttf" if have_ttf else "simsun.ttc"
        if have_ttf and have_ttc:
            detail = "simsun_extracted.ttf（主）+ simsun.ttc（回退）"
        report("2. 字体文件存在", True, f"fonts/：{detail}")
    else:
        report("2. 字体文件存在", False,
               "fonts/ 里没有 simsun_extracted.ttf 或 simsun.ttc，引擎会抛 RuntimeError。"
               "把 SimSun 字体放进 fonts/ 再跑。")


def step_syntax():
    """[3] 语法：scripts/ 下所有 .py 能否编译（捕获写坏/半截的脚本）。"""
    bad = []
    checked = 0
    # 编译到系统临时目录，避免污染仓库；cfile=os.devnull 在 Windows 上是 nul 会被拒绝
    tmpdir = Path(tempfile.mkdtemp(prefix="jrev_smoke_pyc_"))
    try:
        for p in sorted(HERE.glob("*.py")):
            if p.name == "smoke_test.py":
                continue
            checked += 1
            try:
                py_compile.compile(str(p), doraise=True,
                                   cfile=str(tmpdir / (p.stem + ".pyc")))
            except Exception as e:
                bad.append(f"{p.name}: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if bad:
        report("3. scripts 脚本语法编译", False, "\n".join(bad))
    else:
        report("3. scripts 脚本语法编译", True, f"{checked} 个脚本编译通过")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def step_parsed_artifact():
    """[4] 解析产物：output/parsed_ppt.json 是否存在、结构是否有效。"""
    path = OUT_DIR / "parsed_ppt.json"
    if not path.exists():
        report("4. 解析产物 output/parsed_ppt.json", status="WARN",
               detail="不存在。output/ 是 gitignored 产物——若你是刚 clone，需先把课件放进 ppt/ "
               "并跑解析脚本：python scripts/parse_pdf_lecture.py（PDF）或 python scripts/parse_ppt.py（PPTX）。"
               "在产物齐备之前，覆盖率与渲染步骤将跳过。")
        return False
    try:
        docs = _load_json(path)
        total = sum(len(d.get("pages", [])) for d in docs)
        if not isinstance(docs, list) or total == 0:
            raise ValueError("空文档")
    except Exception as e:
        report("4. 解析产物 output/parsed_ppt.json", False, f"解析失败：{e}")
        return False
    src = list((ROOT / "ppt").glob("*.pdf")) + list((ROOT / "ppt").glob("*.pptx"))
    extra = f"，对应 {len(docs)} 份课件源" if len(docs) else ""
    # 源文件本身被 gitignore，clone 后会缺——只提示，不判失败
    if not src:
        extra += "（注意：ppt/ 源文件缺失，本机无法重新解析，只能验证既有产物）"
    report("4. 解析产物 output/parsed_ppt.json", True,
           f"{total} 页文本{extra}")
    return True


def step_schema(content_path):
    """[5] 内容 JSON schema：合法结构 + 只含引擎允许的块 + 引用图是否在 output/images。"""
    try:
        doc = _load_json(content_path)
    except Exception as e:
        report("5. 内容 JSON schema", False, f"不是合法 JSON：{e}")
        return False
    errors = []
    warns = []
    # 顶层字段
    unknown_top = set(doc) - ALLOWED_TOP
    if unknown_top:
        errors.append(f"顶层未知字段：{sorted(unknown_top)}（只允许 {sorted(ALLOWED_TOP)}）")
    sections = doc.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections 缺失或为空")
        fig_files = []
    else:
        fig_files = []
        for sec in sections:
            for blk in sec.get("blocks", []):
                t = blk.get("type")
                if t not in ALLOWED_BLOCKS:
                    errors.append(f"未知块类型 {t!r}（只允许 {sorted(ALLOWED_BLOCKS)}）")
                    continue
                if t == "para" and blk.get("kind") not in ALLOWED_KIND:
                    errors.append(f"para.kind 只允许 cn/jp/note，实际 {blk.get('kind')!r}")
                if t == "table":
                    rows = blk.get("rows") or []
                    if not rows or not rows[0]:
                        errors.append(f"table.rows 不能为空（{blk}）")
                if t == "figure":
                    f = blk.get("file", "")
                    if not f:
                        errors.append("figure.file 必填")
                    else:
                        fig_files.append(f)
    # 引用图是否存在（gitignored，缺了只警告——重跑解析即可，不算 schema 错）
    if fig_files:
        missing = [f for f in fig_files if not (OUT_DIR / "images" / f).exists()]
        if missing:
            warns.append(f"{len(missing)}/{len(fig_files)} 张引用图不在 output/images，如 {missing[0]}"
                         "（重跑解析脚本可再生成）")
    if errors:
        report("5. 内容 JSON schema", False, "\n".join(errors))
        return False
    if warns:
        report("5. 内容 JSON schema", status="WARN", detail="\n".join(warns))
    else:
        report("5. 内容 JSON schema", True, f"{len(sections)} 节内容，全部块类型合法")
    return True


def step_coverage(content_path, cov_min):
    """[6] 覆盖率：按 SKILL 的官方命令跑 check_coverage，口径同生产。"""
    content = content_path
    if not content.exists():
        report("6. 覆盖率 ≥ 下限", False, f"找不到 {content}")
        return False
    proc = subprocess.run(
        [sys.executable, str(HERE / "check_coverage.py"), str(content)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = proc.stdout + proc.stderr
    m = re.search(r"Pages with >=1 covered term:\s*\d+\s*\((\d+)%\)", text)
    if proc.returncode != 0:
        report("6. 覆盖率 ≥ 下限", False,
               f"check_coverage 非零退出（{proc.returncode}）：\n{text.strip()[-500:]}")
        return False
    if not m:
        report("6. 覆盖率 ≥ 下限", False, f"解析不到覆盖率行：\n{text.strip()[-300:]}")
        return False
    rate = int(m.group(1))
    needs_work = "NEEDS WORK" in text
    ok = rate >= cov_min and not needs_work
    detail = f"{rate}% ≥ {cov_min}%（Verdict 见上方 check_coverage 输出）" if ok \
        else f"{rate}% < {cov_min}% 或 Verdict=NEEDS WORK，未达下限"
    report("6. 覆盖率 ≥ 下限", ok, detail)
    return ok


def _verify_pdf(path, label):
    """验证一个 PDF：有 %PDF 头、非空、能被 fitz 打开且至少 1 页。"""
    if not path.exists() or path.stat().st_size == 0:
        report(label, False, f"{path} 不存在或为空")
        return False
    head = path.read_bytes()[:5]
    if head != b"%PDF-":
        report(label, False, f"{path} 不是 PDF（头部 {head!r}）")
        return False
    import fitz
    try:
        with fitz.open(str(path)) as doc:
            n = doc.page_count
    except Exception as e:
        report(label, False, f"fitz 打不开：{e}")
        return False
    report(label, True, f"生成 {path.name}：{n} 页，PDF 头正常")
    return True


def step_render_b(content_path):
    """[7] 通路 B：内容 JSON → path_b_render → PDF（复用引擎，含表格/红字/图）。"""
    try:
        import path_b_render
    except ImportError as e:
        report("7. 通路 B 渲染（JSON → PDF）", False, f"导入 path_b_render 失败：{e}")
        return False
    try:
        doc = _load_json(content_path)
        out = OUT_DIR / "_smoke_test_b.pdf"
        path_b_render.render(doc, out)
    except Exception as e:
        report("7. 通路 B 渲染（JSON → PDF）", False, f"渲染抛异常：{type(e).__name__}: {e}")
        return False
    finally:
        pass
    return _verify_pdf(out, "7. 通路 B 渲染（JSON → PDF）")


def step_render_a():
    """[8] 通路 A：直写脚本 build_sample_a 产 PDF（引擎的另一种调用方式）。"""
    try:
        import build_sample_a
    except ImportError as e:
        report("8. 通路 A 渲染（直写 → PDF）", False, f"导入 build_sample_a 失败：{e}")
        return False
    old_out = build_sample_a.OUT
    try:
        out = OUT_DIR / "_smoke_test_a.pdf"
        build_sample_a.OUT = str(out)
        build_sample_a.build()
    except Exception as e:
        report("8. 通路 A 渲染（直写 → PDF）", False,
               f"build_sample_a 抛异常：{type(e).__name__}: {e}")
        return False
    finally:
        build_sample_a.OUT = old_out
    return _verify_pdf(out, "8. 通路 A 渲染（直写 → PDF）")


def cleanup_temp():
    for name in ("_smoke_test_a.pdf", "_smoke_test_b.pdf"):
        p = OUT_DIR / name
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="japanese-exam-review 快速冒烟测试")
    ap.add_argument("content", nargs="?", default="examples/content_b_example.json",
                    help="要回归的内容 JSON（默认 examples/content_b_example.json）")
    ap.add_argument("--cov-min", type=int, default=85,
                    help="覆盖率下限 %%：低于即 FAIL（默认 85，与 SKILL 复习模式口径一致）")
    args = ap.parse_args(argv)
    content_path = Path(args.content)
    if not content_path.is_absolute():
        content_path = ROOT / content_path
    args.content = content_path
    if not 0 <= args.cov_min <= 100:
        print("--cov-min 须在 0..100", file=sys.stderr)
        return 2

    print_header(args)

    step_deps()
    step_fonts()
    step_syntax()
    have_parsed = step_parsed_artifact()

    step_schema(content_path)

    if have_parsed:
        step_coverage(content_path, args.cov_min)
    else:
        report("6. 覆盖率 ≥ 下限", status="SKIP", detail="跳过（依赖 output/parsed_ppt.json，见第 4 步）")

    if have_parsed:
        step_render_b(content_path)
    else:
        report("7. 通路 B 渲染（JSON → PDF）", status="SKIP", detail="跳过（output/ 产物缺失）")
    step_render_a()

    # ---- 汇总 ----
    cleanup_temp()
    fails = [r for r in _results if r[1] == "FAIL"]
    warns = [r for r in _results if r[1] == "WARN"]
    skips = [r for r in _results if r[1] == "SKIP"]
    passed = len(_results) - len(fails) - len(warns) - len(skips)
    print()
    print("=" * 64)
    print(f"  通过 {passed}   警告 {len(warns)}   跳过 {len(skips)}   失败 {len(fails)}")
    if warns:
        for _, _, d in warns:
            print(f"  WARN 提示：{str(d).splitlines()[0]}")
    if skips:
        for n, _, _ in skips:
            print(f"  SKIP 项  ：{n}")
    if fails:
        print("\n  ❌ 冒烟未通过。以下项 FAIL：")
        for n, _, _ in fails:
            print(f"     - {n}")
        print("  先按上面 [FAIL] 的指引修，再重跑本脚本。")
        print("  （记住：这只测确定性部件；agent 端到端场景请看 test-prompts.json，用 darwin 类全量实测验证。）")
        print("=" * 64)
        return 1
    print("  ✅ 冒烟全部通过——skill 的确定性部件（依赖/字体/解析产物/schema/覆盖率/A+B 渲染）都还活着。")
    print("  注：图的存在性、真实考卷考点库、agent 3 场景端到端不在本脚本范围。")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
