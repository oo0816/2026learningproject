"""Parse PDF exam papers: extract text → JSON."""
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF


def parse_pdf(filepath):
    """Parse a single PDF and return page-by-page text."""
    filename = filepath.name
    doc = fitz.open(str(filepath))
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        # Normalize whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        pages.append({
            "page": page_num + 1,
            "text": "\n".join(lines)
        })

    doc.close()
    return {"filename": filename, "page_count": len(pages), "pages": pages}


def main():
    exams_dir = Path("exams")
    if not exams_dir.exists():
        print(json.dumps({"error": "exams/ directory not found"}, ensure_ascii=False))
        sys.exit(1)

    pdf_files = sorted(exams_dir.glob("*.pdf"))
    if not pdf_files:
        print(json.dumps({"error": "No .pdf files found in exams/"}, ensure_ascii=False))
        sys.exit(1)

    all_results = []
    for pdf_file in pdf_files:
        result = parse_pdf(pdf_file)
        all_results.append(result)

    output_path = Path("output/parsed_exams.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "ok",
        "files_parsed": len(all_results),
        "total_pages": sum(r["page_count"] for r in all_results),
        "output": str(output_path)
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
