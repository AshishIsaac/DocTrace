import json

import pytest

from doctrace.extract import extract


def test_pdf_pages(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for text in ["first page text", "second page about normalization"]:
        doc.new_page().insert_text((50, 72), text)
    path = tmp_path / "a.pdf"
    doc.save(path)
    segs = extract(str(path), ".pdf")
    assert [loc for loc, _ in segs] == ["page 1", "page 2"]
    assert "normalization" in segs[1][1]
    # bytes input works too (Google Drive downloads)
    assert extract(path.read_bytes(), ".pdf")[1][0] == "page 2"


def test_docx_sections_and_tables(tmp_path):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_heading("Deadlock", 1)
    d.add_paragraph("Coffman conditions")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "SJF", "No"
    d.save(tmp_path / "a.docx")
    segs = dict(extract(str(tmp_path / "a.docx"), ".docx"))
    assert "Coffman" in segs['section "Deadlock"']
    assert "SJF | No" in segs["table 1"]


def test_pptx_slides(tmp_path):
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "TCP vs UDP"
    prs.save(tmp_path / "a.pptx")
    assert extract(str(tmp_path / "a.pptx"), ".pptx") == [("slide 1", "TCP vs UDP")]


def test_xlsx_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.title = "Marks"
    wb.active.append(["DBMS", 28])
    wb.save(tmp_path / "a.xlsx")
    assert extract(str(tmp_path / "a.xlsx"), ".xlsx") == [('sheet "Marks"', "DBMS | 28")]


def test_text_html_notebook(tmp_path):
    (tmp_path / "a.md").write_bytes(b"# Title\nbody")
    assert extract(str(tmp_path / "a.md"), ".md") == [("", "# Title\nbody")]

    (tmp_path / "a.html").write_text("<p>Hi&amp;bye</p><script>x()</script>", encoding="utf-8")
    text = extract(str(tmp_path / "a.html"), ".html")[0][1]
    assert "Hi&bye" in text
    assert "x()" not in text

    nb = {"cells": [{"cell_type": "markdown", "source": ["Gradient ", "descent"]}]}
    (tmp_path / "a.ipynb").write_text(json.dumps(nb), encoding="utf-8")
    assert extract(str(tmp_path / "a.ipynb"), ".ipynb") == [("cell 1", "Gradient descent")]


def test_non_utf8_text(tmp_path):
    (tmp_path / "a.txt").write_bytes("café".encode("cp1252"))
    assert extract(str(tmp_path / "a.txt"), ".txt") == [("", "café")]


def test_unknown_extension():
    assert extract(b"whatever", ".doc") == []
