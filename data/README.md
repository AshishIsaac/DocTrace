# Put your files here

Drop your documents into this folder in any folder / sub-folder layout you like, e.g.

```
data/
  Semester 3/
    DBMS/
      Unit 2 - Normalization.pdf
      Lab manual.docx
    OS/
      Scheduling slides.pptx
```

Then run `python ingest.py`. The folder structure is kept and shown in the search
results, so you always see exactly where a match lives.

Supported: PDF, DOCX, PPTX, XLSX, TXT/MD/CSV/JSON, HTML, Jupyter notebooks, source
code, and images / scanned PDFs (with Tesseract OCR installed).

Everything in this folder except this README is ignored by git.
