from pathlib import Path

import pytest

CORPUS = Path("/corpus") if Path("/corpus/raw").exists() else Path(__file__).resolve().parents[1] / "corpus"


@pytest.mark.skipif(not (CORPUS / "raw").exists(), reason="corpus not available")
def test_table10_note_b_is_its_own_clause():
    pypdf = pytest.importorskip("pypdf")
    from bpc.retriever.chunking import chunk_document

    reader = pypdf.PdfReader(str(CORPUS / "raw/bda_rmp2015_zoning_regulations.pdf"))
    pages = [p.extract_text() or "" for p in reader.pages]
    chunks = {c.chunk_id: c for c in chunk_document("ZR2015", "RMP-2015 ZR", "ZR", pages)}
    note = chunks["ZR2015:T10:ii.b"]
    assert "road width is less than 9.0 m" in note.text and "11.5" in note.text
    assert "Table 10" in note.header and "Residential (Main)" in note.header
    assert "ZR2015:T8" in chunks and "Width of site" in chunks["ZR2015:T8"].text
    assert "ZR2015:T8" in chunks["ZR2015:T10:ii.a"].refs
