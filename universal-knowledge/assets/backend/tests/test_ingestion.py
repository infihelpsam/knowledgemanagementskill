import io
import pytest
from docx import Document
from pypdf import PdfWriter
from knowledge.ingestion import chunks, extract, normalize, fingerprint


@pytest.mark.parametrize('filename,content,expected', [
    ('a.txt', b'hello\x00 world', 'hello world'),
    ('a.md', b'# Heading\nEvidence', '# Heading\nEvidence'),
    ('a.csv', b'name,value\nanswer,42', 'name | value\nanswer | 42'),
    ('a.html', b'<script>bad()</script><p>Evidence</p>', 'Evidence'),
])
def test_formats(filename, content, expected):
    assert extract(content, filename, 10000, 10000) == expected


def test_docx_and_pdf():
    stream = io.BytesIO()
    doc = Document()
    doc.add_paragraph('Warranty lasts two years')
    doc.save(stream)
    assert 'two years' in extract(stream.getvalue(), 'a.docx', 100000, 10000)
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b'BT /F1 12 Tf 10 100 Td (Warranty two years) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(content)
    pdf = io.BytesIO()
    writer.write(pdf)
    assert 'Warranty two years' in extract(pdf.getvalue(), 'a.pdf', 100000, 10000)


def test_limits_and_unsupported():
    for content, name, maximum, chars in [(b'long', 'a.txt', 2, 10), (b'long', 'a.txt', 10, 2), (b'x', 'a.exe', 10, 10), (b'', 'a.txt', 10, 10)]:
        with pytest.raises(ValueError):
            extract(content, name, maximum, chars)


def test_chunk_provenance_and_dedup():
    text = '0123456789' * 100
    pieces = list(chunks(text, 100, 20))
    assert pieces[0]['start'] == 0 and pieces[-1]['end'] == len(text)
    for piece in pieces:
        assert text[piece['start']:piece['end']] == piece['text']
    assert fingerprint(normalize('a  b')) == fingerprint(normalize('a b'))
    with pytest.raises(ValueError):
        list(chunks(text, 20, 20))
