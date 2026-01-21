"""
PDF Chunker for Large Documents
Splits large PDFs into manageable chunks for Claude Code processing
"""

import os
import json
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("Installing pypdf...")
    os.system("pip install pypdf -q")
    from pypdf import PdfReader, PdfWriter


def split_pdf(input_path: str, output_dir: str = "pdf_chunks", pages_per_chunk: int = 50):
    """
    Split a large PDF into smaller chunks for RAG processing

    Args:
        input_path: Path to the input PDF
        output_dir: Directory to save chunks
        pages_per_chunk: Maximum pages per chunk (keep under 50 for Claude)
    """
    Path(output_dir).mkdir(exist_ok=True)

    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    print(f"Total pages: {total_pages}")
    print(f"Creating chunks of {pages_per_chunk} pages each...")

    chunks_info = []
    chunk_num = 1

    for start_page in range(0, total_pages, pages_per_chunk):
        end_page = min(start_page + pages_per_chunk, total_pages)

        writer = PdfWriter()
        for page_num in range(start_page, end_page):
            writer.add_page(reader.pages[page_num])

        output_filename = f"chunk_{chunk_num:02d}_pages_{start_page+1}-{end_page}.pdf"
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "wb") as f:
            writer.write(f)

        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB

        chunk_info = {
            "chunk": chunk_num,
            "filename": output_filename,
            "pages": f"{start_page+1}-{end_page}",
            "size_mb": round(file_size, 2)
        }
        chunks_info.append(chunk_info)

        print(f"  Created: {output_filename} ({file_size:.2f} MB)")
        chunk_num += 1

    # Save index
    index_path = os.path.join(output_dir, "chunks_index.json")
    with open(index_path, "w") as f:
        json.dump({
            "source": input_path,
            "total_pages": total_pages,
            "chunks": chunks_info
        }, f, indent=2)

    print(f"\nCreated {len(chunks_info)} chunks in {output_dir}/")
    print(f"Index saved to {index_path}")

    return chunks_info


def extract_text_from_chunk(chunk_path: str) -> str:
    """Extract text from a PDF chunk for embedding/search"""
    reader = PdfReader(chunk_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n\n"
    return text


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_chunker.py <path_to_pdf> [pages_per_chunk]")
        print("Example: python pdf_chunker.py sornette_book.pdf 50")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    split_pdf(pdf_path, pages_per_chunk=pages)
