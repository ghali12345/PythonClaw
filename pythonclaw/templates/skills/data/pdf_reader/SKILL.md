---
name: pdf_reader
description: >
  Extract text content from PDF files. Supports multi-page PDFs,
  page-level extraction, and metadata reading. Use when the user asks
  to read, extract, or analyze content from a PDF document.
---

## Instructions

Extract text and metadata from PDF files.

### Prerequisites

Install dependency: `pip install PyPDF2`

### Usage

```bash
python {skill_path}/read_pdf.py PATH_TO_PDF [options]
```

Options:
- `--pages 1-5` — extract only specific pages (1-indexed, supports ranges)
- `--metadata` — include PDF metadata (author, title, creation date)
- `--format json` — output as JSON
- `--summary` — show page count and character count overview only

### Examples

- "Read this PDF" → `python {skill_path}/read_pdf.py document.pdf`
- "Extract pages 2-4 from report.pdf" → `python {skill_path}/read_pdf.py report.pdf --pages 2-4`
- "What's in this PDF?" → `python {skill_path}/read_pdf.py file.pdf --summary`
- "Get PDF metadata" → `python {skill_path}/read_pdf.py file.pdf --metadata`

## Resources

| File | Description |
|------|-------------|
| `read_pdf.py` | PDF text extractor |
