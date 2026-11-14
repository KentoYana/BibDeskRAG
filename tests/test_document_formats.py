"""Generated documents only: no real library, Office apps, network or macro execution."""
import base64
from dataclasses import replace
import hashlib
import io
import plistlib
import struct
import zipfile

import pytest

from bibdesk_rag.config import Config
from bibdesk_rag.database import connect, doctor
from bibdesk_rag.extractors import ExtractionOptions, extract_file
from bibdesk_rag.extractors.iwork import snappy
from bibdesk_rag.extractors.common import ExpansionBudget
from bibdesk_rag.indexer import index_library
from bibdesk_rag.search import SQLiteSearch


from tools.format_fixtures import package, vint, pb, iwa, docx, pptx, binary_doc, binary_xls, numbers


@pytest.mark.parametrize('suffix,factory,status', [
    ('.docx', docx, 'ok'), ('.pptx', pptx, 'ok'), ('.doc', binary_doc, 'partial'),
    ('.xls', binary_xls, 'partial'), ('.numbers', numbers, 'partial'),
])
def test_generated_formats_preserve_hash_and_provenance(tmp_path, suffix, factory, status):
    source = tmp_path / ('generated' + suffix)
    source.write_bytes(factory())
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = extract_file(source)
    assert result.status == status, result.error
    assert any('RecQ' in c.text for c in result.chunks), result
    assert all(c.source_type == suffix[1:] for c in result.chunks)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    if suffix == '.pptx':
        assert result.chunks[0].page_start == 1 and 'First' in result.chunks[0].text
        assert result.chunks[-1].page_start == 2 and 'Second' in result.chunks[-1].text
        assert any('Speaker notes' in c.text for c in result.chunks)
    elif suffix in {'.xls', '.numbers'}:
        chunk = result.chunks[0]
        assert chunk.sheet_name == 'Genes' and chunk.row_start == chunk.row_end == 2
        assert '42' in chunk.text
    else:
        assert all(c.member_path for c in result.chunks)


@pytest.mark.parametrize('suffix', ['.key', '.pages', '.numbers'])
@pytest.mark.parametrize('nested', [False, True])
def test_iwork_only_known_text_fields_no_metadata_or_media(tmp_path, suffix, nested):
    data = iwa([(1, 2001, pb((3, '日本語 RecQ'.encode()))),
                (2, 999, pb((3, b'PRIVATE_STYLE_METADATA')))])
    parts = {'Index/Document.iwa': data}
    if nested:
        parts = {'Index.zip': package({'Document.iwa': data})}
    source = tmp_path / ('text' + suffix)
    source.write_bytes(package({**parts, 'Data/ignored.png': b'PRIVATE_IMAGE'}))
    result = extract_file(source)
    assert result.status == 'partial', result.error
    assert [c.text for c in result.chunks] == ['日本語 RecQ']
    assert '#object=1;text=1' in result.chunks[0].member_path
    assert result.chunks[0].page_start is None


def test_iwork_xml_and_tex_source_never_include_other_files(tmp_path):
    source = tmp_path / 'legacy.pages'
    source.write_bytes(package({'index.xml': '<sf:document xmlns:sf="http://developer.apple.com/'
                               'namespaces/sf"><sf:p>RecQ XML</sf:p></sf:document>'}))
    assert extract_file(source).chunks[0].text == 'RecQ XML'
    secret = tmp_path / 'secret.tex'
    secret.write_text('MUST_NOT_BE_READ')
    tex = tmp_path / 'source.tex'
    tex.write_text('日本語 RecQ\n\\input{secret.tex}\n\\write18{touch forbidden}\n')
    result = extract_file(tex)
    assert result.status == 'ok'
    assert 'MUST_NOT_BE_READ' not in str(result)
    assert result.chunks[0].row_start == result.chunks[0].row_end == 1
    assert not (tmp_path / 'forbidden').exists()


@pytest.mark.parametrize('suffix', ['.docx', '.pptx', '.key', '.pages', '.numbers'])
def test_containers_refuse_traversal_and_dtd(tmp_path, suffix):
    source = tmp_path / ('unsafe' + suffix)
    source.write_bytes(package({'../escape.xml': b'data'}))
    result = extract_file(source)
    assert result.status == 'error' and 'Unsafe ZIP member' in result.error
    assert not result.chunks
    part = 'ppt/presentation.xml' if suffix == '.pptx' else (
        'word/document.xml' if suffix == '.docx' else 'index.xml')
    source.write_bytes(package({part: '<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]>'
                                    '<x>&a;</x>'}))
    result = extract_file(source)
    assert result.status == 'error' and 'DTDForbidden' in result.error


def test_iwa_bounds_and_shared_nested_container_budget(tmp_path):
    options = ExtractionOptions()
    with pytest.raises(ValueError, match='copy bounds'):
        snappy(b'\x05\x01\x01', options, ExpansionBudget(options))
    with pytest.raises(ValueError, match='max_file_bytes'):
        snappy(vint(options.max_file_bytes + 1), options, ExpansionBudget(options))
    inner = docx()
    outer = tmp_path / 'archive.zip'
    outer.write_bytes(package({'first.docx': inner, 'second.docx': inner}))
    with zipfile.ZipFile(io.BytesIO(inner)) as archive:
        expanded = sum(i.file_size for i in archive.infolist())
    result = extract_file(outer, replace(options, max_archive_bytes=2 * len(inner) + expanded))
    assert result.status == 'partial' and len(result.chunks) == 2
    assert result.chunks[0].member_path.startswith('first.docx!/word/document.xml#')
    assert result.members[1]['status'] == 'error' and 'expanded size' in result.error


@pytest.mark.parametrize('suffix', ['.JPG', '.png', '.svg', '.mp4', '.mov', '.webm'])
def test_explicit_media_exclusion_without_reading(tmp_path, monkeypatch, suffix):
    source = tmp_path / ('media' + suffix)
    source.write_bytes(b'not parsed')
    def forbidden(*args, **kwargs):
        raise AssertionError('Excluded media must not be read')
    monkeypatch.setattr(type(source), 'open', forbidden)
    result = extract_file(source, ExtractionOptions(max_file_bytes=1))
    assert result.status == 'excluded' and not result.chunks


def test_zip_media_excluded_and_other_new_formats_indexed(tmp_path):
    source = tmp_path / 'mixed.zip'
    source.write_bytes(package({'photo.jpg': b'not parsed', 'video.mp4': b'not parsed',
                                'methods.tex': 'RecQ protocol'}))
    result = extract_file(source)
    assert result.status == 'ok'
    assert [m['status'] for m in result.members] == ['excluded', 'excluded', 'ok']
    assert result.chunks[0].member_path == 'methods.tex'


def test_upgrade_retries_new_formats_without_reextracting_existing_formats(tmp_path, monkeypatch):
    import bibdesk_rag.indexer as indexer
    from bibdesk_rag.extractors import ExtractionResult
    tex = tmp_path / 'methods.tex'
    tex.write_text('RecQ evidence')
    other = tmp_path / 'same.csv'
    other.write_text('gene,value\ncontrol,2\n')
    media = tmp_path / 'movie.mp4'
    media.write_bytes(b'large ignored media')
    bib = tmp_path / 'refs.bib'
    fields = ''
    for index, path in enumerate((tex, other, media), 1):
        locator = base64.b64encode(plistlib.dumps({'relativePath': path.name})).decode()
        fields += f'Bdsk-File-{index}={{{locator}}},'
    bib.write_text('@article{Example,title={Test},' + fields + '}')
    config = Config(bib, tmp_path / 'index.sqlite3')
    original = indexer.extract_file
    def previous(path, options):
        if path.suffix == '.tex':
            return ExtractionResult(status='unsupported')
        return original(path, options)
    monkeypatch.setattr(indexer, 'extract_file', previous)
    index_library(config)
    with connect(config.database) as db:
        db.execute("DELETE FROM settings WHERE key='extraction_revision'")
    monkeypatch.setattr(indexer, 'extract_file', original)
    report = index_library(config)
    assert report['files_extracted'] == 1 and report['files_reused'] == 2
    db = connect(config.database, readonly=True)
    search = SQLiteSearch(db)
    matches = search.search_fulltext('RecQ', citekeys=['Example'])
    assert len(matches) == 1 and matches[0]['row_start'] == 1
    assert matches[0]['source_type'] == 'tex' and matches[0]['citekey'] == 'Example'
    attachments = search.get_attachments('Example')
    movie = next(a for a in attachments if a['file_path'].endswith('.mp4'))
    assert movie['extraction_status'] == 'excluded' and movie['content_hash'] is None
    assert not any(r['path'].endswith('.mp4') for r in doctor(db)['extraction_failures'])
    db.close()


def test_iwork_directory_package_incremental_updates_and_collision_safety(tmp_path):
    root = tmp_path / 'linked.pages'
    root.mkdir()
    index = root / 'Index'
    index.mkdir()
    body = index / 'Document.iwa'
    body.write_bytes(iwa([(1, 2001, pb((3, b'RecQ original')))]))
    outside = tmp_path / 'outside.pages'
    outside.mkdir()
    (outside / 'unlinked.iwa').write_bytes(b'must not inspect')
    locator = base64.b64encode(plistlib.dumps({'relativePath': root.name})).decode()
    bib = tmp_path / 'refs.bib'
    bib.write_text('@article{Package,title={Example},Bdsk-File-1={' + locator + '}}')
    original = {p: p.read_bytes() for p in (bib, body)}
    config = Config(bib, tmp_path / 'index.sqlite3')
    assert index_library(config)['files_extracted'] == 1
    assert index_library(config)['files_reused'] == 1
    assert index_library(config, verify_hashes=True)['files_reused'] == 1
    db = connect(config.database, readonly=True)
    search = SQLiteSearch(db)
    hit = search.search_fulltext('RecQ')[0]
    assert hit['member_path'] == 'Index/Document.iwa#object=1;text=1'
    assert hit['extraction_status'] == 'partial' and 'iWork' in hit['extraction_warning']
    db.close()
    assert {p: p.read_bytes() for p in original} == original
    # A contained source changed while the package root itself did not.
    body.write_bytes(iwa([(1, 2001, pb((3, b'changed evidence')))]))
    assert index_library(config)['files_extracted'] == 1
    with pytest.raises(ValueError, match='overlaps'):
        Config(bib, root / 'index.sqlite3').protect_sources([root])
    hardlink = tmp_path / 'hardlink.sqlite3'
    hardlink.hardlink_to(body)
    with pytest.raises(ValueError, match='overlaps'):
        Config(bib, hardlink).protect_sources([root])
    link = index / 'escape.iwa'
    link.symlink_to(outside / 'unlinked.iwa')
    result = extract_file(root)
    assert result.status == 'error' and 'symlink' in result.error
    assert not result.chunks


def test_numbers_decimal_precision():
    from bibdesk_rag.extractors.iwork import _cell
    coefficient = 1234567890123456789012345678901234
    bits = coefficient | (6176 << 113)
    data = bytes([5, 2]) + b'\0' * 6 + struct.pack('<I', 1) + bits.to_bytes(16, 'little')
    assert _cell(data, {}) == str(coefficient)


def test_doc_cached_field_results_only_and_encryption_refusal(tmp_path):
    source = tmp_path / 'fields.doc'
    source.write_bytes(binary_doc('RecQ \x13HYPERLINK dangerous\x14shown\x15\r'))
    result = extract_file(source)
    assert result.status == 'partial'
    assert result.chunks[0].text == 'RecQ shown'
    data = bytearray(source.read_bytes())
    struct.pack_into('<H', data, 512 * 3 + 10, 0x100)
    source.write_bytes(data)
    result = extract_file(source)
    assert result.status == 'error' and 'Encrypted' in result.error
    assert not result.chunks


def test_chunk_limit_and_archive_policy_upgrade(tmp_path, monkeypatch):
    import bibdesk_rag.indexer as indexer
    from bibdesk_rag.extractors import ExtractionResult
    source = tmp_path / 'evidence.zip'
    source.write_bytes(package({'methods.docx': docx(), 'notes.tex': 'RecQ source'}))
    locator = base64.b64encode(plistlib.dumps({'relativePath': source.name})).decode()
    bib = tmp_path / 'refs.bib'
    bib.write_text('@article{Archive,title={Example},Bdsk-File-1={' + locator + '}}')
    config = Config(bib, tmp_path / 'index.sqlite3')
    original = indexer.extract_file
    monkeypatch.setattr(indexer, 'extract_file', lambda *args: ExtractionResult(status='no_text'))
    index_library(config)
    with connect(config.database) as db:
        db.execute("DELETE FROM settings WHERE key='extraction_revision'")
    monkeypatch.setattr(indexer, 'extract_file', original)
    assert index_library(config)['files_extracted'] == 1
    result = extract_file(source, ExtractionOptions(max_chunks=1))
    assert result.status == 'partial' and len(result.chunks) == 1
    assert 'Chunk limit' in result.error


@pytest.mark.parametrize('strict', [False, True])
def test_docx_textboxes_not_duplicated_and_strict_namespaces(tmp_path, strict):
    namespace = ('http://purl.oclc.org/ooxml/wordprocessingml/main' if strict else
                 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
    source = tmp_path / 'textboxes.docx'
    xml = (f'<w:document xmlns:w="{namespace}"><w:body><w:p><w:r><w:t>Outer</w:t>'
           '</w:r><w:txbxContent><w:p><w:r><w:t>Inner</w:t></w:r></w:p></w:txbxContent>'
           '</w:p></w:body></w:document>')
    source.write_bytes(package({'word/document.xml': xml}))
    result = extract_file(source)
    assert result.status == 'ok', result.error
    assert [c.text for c in result.chunks] == ['Outer', 'Inner']


def test_iwork_directory_shares_member_budget_with_index_zip(tmp_path):
    root = tmp_path / 'nested.pages'
    root.mkdir()
    (root / 'empty').mkdir()
    (root / 'Index.zip').write_bytes(package({'Document.iwa': iwa([(1, 2001, pb((3, b'RecQ')))])}))
    result = extract_file(root, ExtractionOptions(max_archive_members=2))
    assert result.status == 'error' and 'member count' in result.error
    assert not result.chunks
