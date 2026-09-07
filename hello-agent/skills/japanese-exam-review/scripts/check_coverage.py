"""Coverage checker: compare parsed slides against a Path-B content JSON.

Current schema blocks handled: para / heading / exam / figure / table
(old reportlab-era term_table / concept_card are gone — no longer counted).

Usage:
    python scripts/check_coverage.py <content.json>

Reads parsed text from output/parsed_ppt.json (run a parser first).
Reports pages whose text matches none of the content's covered terms.
The parsed path is anchored to the skill root, so this runs from any cwd.
"""
import json
import re
import sys
from pathlib import Path


def extract_terms(text):
    """Extract potential technical terms from Japanese text.
    Simple heuristic: 2+ kanji/katakana/acronym sequences.
    """
    katakana = re.findall(r"[゠-ヿ･-ﾟ]{2,}", text)
    kanji = re.findall(r"[一-鿿]{2,}", text)
    english = re.findall(r"[A-Z]{2,}", text)
    return set(katakana + kanji + english)


def covered_terms_from(content):
    """Collect terms the content actually covers (new schema block types)."""
    terms = set()

    def add_text(*parts):
        for p in parts:
            if isinstance(p, str) and p.strip():
                terms.update(extract_terms(p))

    for section in content.get("sections", []):
        add_text(section.get("jp", ""), section.get("cn", ""))
        for block in section.get("blocks", []):
            kind = block.get("type")
            if kind in ("para", "heading", "exam"):
                add_text(block.get("text", ""))
            elif kind == "figure":
                add_text(block.get("caption_cn", ""), block.get("caption_detail", ""))
            elif kind == "table":
                cells = list(block.get("headers", []))
                for row in block.get("rows", []):
                    cells += [str(c) for c in row]
                add_text(" ".join(cells))
            # unknown block type -> ignore (renderer would also reject it)
    return terms


def main():
    # Anchor output/ to the skill root (this file lives in <skill-root>/scripts/),
    # so the checker works regardless of the caller's working directory.
    parsed_path = Path(__file__).resolve().parent.parent / "output" / "parsed_ppt.json"
    if len(sys.argv) < 2:
        print("usage: python scripts/check_coverage.py <content.json>")
        sys.exit(2)
    content_path = Path(sys.argv[1])

    if not parsed_path.exists():
        print("ERROR: output/parsed_ppt.json not found. Run a parser first.")
        sys.exit(1)
    if not content_path.exists():
        print(f"ERROR: {content_path} not found.")
        sys.exit(1)

    with open(parsed_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    covered_terms = covered_terms_from(content)

    total_pages = 0
    uncovered_pages = []

    for doc in parsed:
        for page in doc.get("pages", []):
            total_pages += 1
            page_text = page.get("text", "")
            if not page_text.strip():
                continue  # image-only / blank page

            page_terms = extract_terms(page_text)
            matched = page_terms & covered_terms
            if not matched:
                noise = {"の", "こと", "する", "いる", "ある", "なる", "これ", "それ", "ため",
                         "よう", "など", "ます", "です", "から", "まで", "より", "The",
                         "This", "For", "Are", "Not", "All", "Its", "Can", "Has", "One"}
                significant = {t for t in page_terms - covered_terms if t not in noise and len(t) > 2}
                if significant:
                    uncovered_pages.append({
                        "doc": doc.get("filename", "?"),
                        "page": page.get("page", "?"),
                        "sample_terms": list(significant)[:8],
                    })

    covered_count = total_pages - len(uncovered_pages)
    rate = (covered_count / total_pages * 100) if total_pages else 0

    print(f"=== Coverage Report ===")
    print(f"Total pages: {total_pages}")
    print(f"Pages with >=1 covered term: {covered_count} ({rate:.0f}%)")
    print(f"Pages with 0 coverage: {len(uncovered_pages)}")
    print(f"Covered term pool: {len(covered_terms)} terms")
    print()

    if uncovered_pages:
        print("=== Pages with NO coverage ===")
        for item in uncovered_pages:
            terms_str = ", ".join(item["sample_terms"][:5])
            print(f"  {item['doc']} p{item['page']}: {terms_str}")
        print()

    if rate >= 85:
        print("Verdict: GOOD — coverage is solid.")
    elif rate >= 70:
        print("Verdict: OK — review the uncovered pages above.")
    else:
        print("Verdict: NEEDS WORK — significant gaps. Review and add missing content.")


if __name__ == "__main__":
    main()
