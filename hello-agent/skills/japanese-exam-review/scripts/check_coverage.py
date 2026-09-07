"""Coverage checker: compare parsed slides against content JSON.
Reports pages with no coverage and potential missed terms.
"""
import json
import sys
from pathlib import Path
from collections import Counter


def extract_terms(text):
    """Extract potential technical terms from Japanese text.
    Simple heuristic: 2+ kanji/katakana sequences.
    """
    import re
    # Katakana words (2+ chars)
    katakana = re.findall(r'[゠-ヿ･-ﾟ]{2,}', text)
    # Kanji compounds (2+ chars)
    kanji = re.findall(r'[一-鿿]{2,}', text)
    # English acronyms (2+ uppercase)
    english = re.findall(r'[A-Z]{2,}', text)
    return set(katakana + kanji + english)


def main():
    parsed_path = Path("output/parsed_ppt.json")
    content_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/content_mode1.json")

    if not parsed_path.exists():
        print("ERROR: output/parsed_ppt.json not found. Run parser first.")
        sys.exit(1)
    if not content_path.exists():
        print(f"ERROR: {content_path} not found.")
        sys.exit(1)

    with open(parsed_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    # Collect all covered terms from content JSON
    covered_terms = set()
    for section in content.get("sections", []):
        for block in section.get("blocks", []):
            if block["type"] == "term_table":
                for row in block.get("rows", []):
                    if row:
                        covered_terms.add(row[0])  # Japanese term column
                        covered_terms.update(extract_terms(str(row)))
            elif block["type"] == "concept_card":
                covered_terms.update(block.get("keywords", []))
                covered_terms.update(extract_terms(block.get("content", "")))
                covered_terms.update(extract_terms(block.get("translation", "")))
                covered_terms.update(extract_terms(block.get("title", "")))

    # Check each page
    total_pages = 0
    uncovered_pages = []
    page_terms = {}  # page -> top unmatched terms

    for doc in parsed:
        for page in doc.get("pages", []):
            total_pages += 1
            page_text = page.get("text", "")
            if not page_text.strip():
                # Empty page (image-only or blank), skip
                continue

            page_terms_set = extract_terms(page_text)
            matched = page_terms_set & covered_terms
            unmatched = page_terms_set - covered_terms

            if not matched:
                # Filter out obvious non-technical unmatched terms
                noise = {"の", "こと", "する", "いる", "ある", "なる", "これ", "それ", "ため",
                         "よう", "など", "ます", "です", "から", "まで", "より", "The",
                         "This", "For", "Are", "Not", "All", "Its", "Can", "Has", "One"}
                significant = {t for t in unmatched if t not in noise and len(t) > 2}
                if significant:
                    uncovered_pages.append({
                        "doc": doc["filename"],
                        "page": page["page"],
                        "sample_terms": list(significant)[:8]
                    })

    covered_count = total_pages - len(uncovered_pages)
    rate = (covered_count / total_pages * 100) if total_pages else 0

    # Report
    print(f"=== Coverage Report ===")
    print(f"Total pages: {total_pages}")
    print(f"Pages with >=1 term covered: {covered_count} ({rate:.0f}%)")
    print(f"Pages with 0 coverage: {len(uncovered_pages)}")
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
