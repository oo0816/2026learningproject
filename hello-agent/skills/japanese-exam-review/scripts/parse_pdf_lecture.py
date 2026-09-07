"""Parse lecture PDF handouts: extract text + images → JSON.
Used when course materials are PDF slides (not PPTX).
Output format matches parse_ppt.py for compatibility with generate_pdf.py.
"""
import json
import sys
from pathlib import Path
import fitz

OUTPUT_IMAGES = Path("output/images")
OUTPUT_IMAGES.mkdir(parents=True, exist_ok=True)


def parse_lecture_pdf(filepath):
    """Parse a single lecture PDF and return structured data."""
    filename = filepath.name
    doc = fitz.open(str(filepath))
    pages = []
    img_counter = [1]

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Extract embedded images
        images = []
        for img_info in page.get_images(full=True):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                ext = base_image["ext"]
                img_name = f"{filepath.stem}_p{page_num+1}_img{img_counter[0]}.{ext}"
                img_path = OUTPUT_IMAGES / img_name
                with open(img_path, "wb") as f:
                    f.write(base_image["image"])
                images.append({
                    "file": img_name,
                    "width": base_image.get("width", 0),
                    "height": base_image.get("height", 0)
                })
                img_counter[0] += 1
            except Exception:
                pass

        pages.append({
            "page": page_num + 1,
            "text": "\n".join(lines),
            "images": images
        })

    doc.close()
    return {"filename": filename, "page_count": len(pages), "pages": pages}


def main():
    ppt_dir = Path("ppt")
    if not ppt_dir.exists():
        print(json.dumps({"error": "ppt/ directory not found"}, ensure_ascii=False))
        sys.exit(1)

    pdf_files = sorted(ppt_dir.glob("*.pdf"))
    if not pdf_files:
        print(json.dumps({"error": "No .pdf files found in ppt/"}, ensure_ascii=False))
        sys.exit(1)

    all_results = []
    for pdf_file in pdf_files:
        result = parse_lecture_pdf(pdf_file)
        all_results.append(result)
        print(f"Parsed: {pdf_file.name} ({result['page_count']} pages)", file=sys.stderr)

    output_path = Path("output/parsed_ppt.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    total_images = sum(
        sum(len(p.get("images", [])) for p in r["pages"])
        for r in all_results
    )
    print(json.dumps({
        "status": "ok",
        "files_parsed": len(all_results),
        "total_pages": sum(r["page_count"] for r in all_results),
        "total_images_extracted": total_images,
        "output": str(output_path)
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
