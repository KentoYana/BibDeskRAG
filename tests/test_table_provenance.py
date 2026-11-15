"""Generated tables: exact cell spans through splitting, storage and bounded retrieval."""
from contextlib import closing
from dataclasses import replace
import csv
import hashlib
import json
import zipfile

from openpyxl import Workbook
import pytest

from bibdesk_rag import indexer
from bibdesk_rag.config import Config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import SCHEMA_VERSION, connect
from bibdesk_rag.extractors import ExtractionOptions, extract_file
from bibdesk_rag.extractors.common import table_chunks
from bibdesk_rag.search import SQLiteSearch
from tools.format_fixtures import binary_xls, numbers
from tools.package_smoke import synthetic_pdf


def verify_cells(chunks, originals, options):
    coverage = {key: set() for key in originals}
    seen = set()
    for chunk in chunks:
        assert len(chunk.text) <= options.chunk_size
        table = json.loads(chunk.table_json)
        assert 0 < len(table['cells']) <= 32
        for cell in table['cells']:
            key = cell['row'], cell['column']
            seen.add(key)
            original = originals[key]
            start, end = cell['cell_start'], cell['cell_end']
            assert cell['cell_length'] == len(original)
            assert chunk.text[cell['text_start']:cell['text_end']] == original[start:end]
            assert cell['complete'] == (start == 0 and end == len(original))
            coverage[key].update(range(start, end))
    assert seen == originals.keys()
    assert all(coverage[key] == set(range(len(value))) for key, value in originals.items())


@pytest.mark.parametrize('options', [ExtractionOptions(),
    ExtractionOptions(chunk_size=80, chunk_overlap=79),
    ExtractionOptions(chunk_size=1, chunk_overlap=0)])
def test_long_numeric_cells_keep_literal_whitespace_and_fragment_ranges(options):
    value = '  ' + '0123456789' * 400 + '\n '
    rows = [(1, ['gene', 'value']), (2, ['RecQ', value])]
    chunks = table_chunks(rows, options, 'csv')
    originals = {(r, c): v for r, values in rows for c, v in enumerate(values, 1)}
    verify_cells(chunks, originals, options)
    fragments = [c for chunk in chunks for c in json.loads(chunk.table_json)['cells']
                 if c['row'] == 2 and c['column'] == 2]
    assert len(fragments) > 1 and all(not c['complete'] for c in fragments)


def test_wide_headers_and_many_empty_columns_are_bounded_and_lossless():
    headers = [('label ' + str(i)) * 500 for i in range(70)]
    rows = [(1, headers), (2, ['' if i % 2 else 'value' for i in range(70)])]
    options = ExtractionOptions(chunk_size=1500, chunk_overlap=200)
    chunks = table_chunks(rows, options, 'xlsx', 'Genes')
    verify_cells(chunks, {(r, c): v for r, values in rows for c, v in enumerate(values, 1)}, options)
    assert all(c.sheet_name == 'Genes' for c in chunks)


@pytest.mark.parametrize('start,count', [(1, 0), (3, 2), (1, 1)])
def test_configured_headers_keep_blank_leading_rows_and_headerless_first_record(start, count):
    rows = [(1, []), (2, ['  ', '']), (3, ['gene', 'measurement']),
            (4, ['name', 'units']), (5, ['RecQ', '42'])]
    options = ExtractionOptions(table_header_start=start, table_header_rows=count)
    chunks = table_chunks(rows, options, 'tsv')
    verify_cells(chunks, {(r, c): v for r, values in rows for c, v in enumerate(values, 1)}, options)
    for chunk in chunks:
        table = json.loads(chunk.table_json)
        assert table['header_status'] == ('assumed' if count else 'none')
        for cell in table['cells']:
            assert cell['kind'] == ('header' if start <= cell['row'] < start + count else 'data')
    no_header = table_chunks([(1, ['RecQ', '42'])], replace(options, table_header_rows=0), 'csv')
    assert no_header[0].row_start == 1 and 'RecQ' in no_header[0].text


@pytest.mark.parametrize('field,value', [('table_header_start', 0), ('table_header_rows', -1),
    ('table_header_rows', True), ('table_header_start', 1.5), ('table_header_rows', 101)])
def test_header_option_validation(field, value):
    with pytest.raises(ValueError):
        ExtractionOptions(**{field: value})


@pytest.mark.parametrize('suffix', ['csv', 'tsv', 'xlsx', 'xls', 'numbers'])
def test_shared_table_formats_and_nested_zip_keep_cell_and_source_locations(tmp_path, suffix):
    value = '0123456789' * 400
    path = tmp_path / ('table.' + suffix)
    if suffix in {'csv', 'tsv'}:
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t' if suffix == 'tsv' else ',')
            writer.writerows([['gene', 'value'], [value, '42']])
    elif suffix == 'xlsx':
        book = Workbook()
        book.active.title = 'Genes'
        book.active.append(['gene', 'value'])
        book.active.append([value, '42'])
        book.save(path)
    else:
        path.write_bytes((binary_xls if suffix == 'xls' else numbers)(value))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    options = ExtractionOptions()
    result = extract_file(path, options)
    assert result.status == ('partial' if suffix in {'xls', 'numbers'} else 'ok'), result.error
    # These parsers expose stored values; BIFF converts numeric 42 to literal 42.0.
    numeric = '42.0' if suffix in {'xls', 'numbers'} else '42'
    originals = {(1, 1): 'gene', (1, 2): 'value', (2, 1): value, (2, 2): numeric}
    verify_cells(result.chunks, originals, options)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    archive = tmp_path / 'supplement.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.write(path, 'nested/' + path.name)
    zipped = extract_file(archive, options)
    verify_cells(zipped.chunks, originals, options)
    assert all(c.member_path.startswith('nested/' + path.name) for c in zipped.chunks)
    if suffix in {'xlsx', 'xls', 'numbers'}:
        assert all(c.sheet_name == 'Genes' for c in zipped.chunks)
    if suffix == 'numbers':
        assert all(';table' in c.member_path for c in zipped.chunks)


def assert_visible_cells(text, table, original):
    for cell in table['cells']:
        value = original[cell['row'], cell['column']]
        assert text[cell['text_start']:cell['text_end']] == value[cell['cell_start']:cell['cell_end']]
        assert cell['text_end'] <= len(text)
        assert cell['complete'] == (cell['cell_start'] == 0 and cell['cell_end'] == len(value))


def test_search_chunk_and_budgeted_context_report_only_visible_cell_fragments(tmp_path):
    value = 'prefix ' * 130 + 'Needle ' + ' 0123456789' * 400
    csv_path = tmp_path / 'table.csv'
    with csv_path.open('w', newline='') as stream:
        csv.writer(stream).writerows([['gene', 'value'], ['RecQ', value]])
    bib = tmp_path / 'refs.bib'
    bib.write_text('@article{A,title={Table},Bdsk-File-1={table.csv}}')
    config = Config(bib, tmp_path / 'db.sqlite3')
    indexer.index_library(config)
    originals = {(1, 1): 'gene', (1, 2): 'value', (2, 1): 'RecQ', (2, 2): value}
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        hits = engine.search_fulltext('Needle')
        assert hits
        for hit in hits:
            assert_visible_cells(hit['snippet'], hit['table_provenance'], originals)
            for size in (1, 50, 1000, 20000):
                chunk = engine.get_chunk(hit['chunk_id'], max_chars=size)
                assert_visible_cells(chunk['text'], chunk['table_provenance'], originals)
        for budget in (256, 1000, 2000, 10000):
            context = build_context(engine, 'Needle', max_chars=budget)
            assert len(context['context']) <= budget
            for result in context['results']:
                assert_visible_cells(result['text'], result['table_provenance'], originals)
                assert 'table_cells' in result
                assert any('fragments' in note for note in context['unverified'])


def old_schema(config):
    with closing(connect(config.database)) as db, db:
        db.execute('ALTER TABLE chunks DROP COLUMN table_json')
        db.execute('PRAGMA user_version=2')
        options = json.loads(db.execute("SELECT value FROM settings WHERE key='extraction_options'").fetchone()[0])
        options.pop('table_header_start')
        options.pop('table_header_rows')
        db.execute("UPDATE settings SET value=? WHERE key='extraction_options'", (json.dumps(options, sort_keys=True),))
        versions = dict(indexer.EXTRACTION_VERSIONS)
        versions.update({s: '1' for s in ('.csv', '.tsv', '.xlsx', '.xls', '.numbers', '.pages', '.key')})
        db.execute("UPDATE settings SET value=? WHERE key='extraction_versions'", (json.dumps(versions),))


@pytest.mark.parametrize('fail', [False, True])
def test_schema2_migration_refreshes_tables_once_preserves_other_chunks_or_rolls_back(tmp_path, monkeypatch, fail):
    csv_path = tmp_path / 'table.csv'
    csv_path.write_text('gene,value\nRecQ,42\n')
    pdf = tmp_path / 'paper.pdf'
    pdf.write_bytes(synthetic_pdf())
    bib = tmp_path / 'refs.bib'
    bib.write_text('@article{A,title={RecQ},Bdsk-File-1={table.csv},Bdsk-File-2={paper.pdf}}')
    config = Config(bib, tmp_path / 'db.sqlite3')
    indexer.index_library(config)
    old_schema(config)
    before = {p: p.read_bytes() for p in (bib, csv_path, pdf, config.database)}
    with closing(connect(config.database, readonly=True)) as db:
        other = [tuple(row) for row in db.execute("SELECT * FROM chunks WHERE source_type='pdf'")]
        assert not SQLiteSearch(db).get_chunk(1).get('table_provenance')
    if fail:
        def crash(*args):
            raise RuntimeError('generated migration failure')
        monkeypatch.setattr(indexer, 'extract_file', crash)
        with pytest.raises(RuntimeError, match='generated migration failure'):
            indexer.index_library(config)
        assert config.database.read_bytes() == before[config.database]
    else:
        report = indexer.index_library(config)
        assert report['files_extracted'] == 1 and report['files_reused'] == 1
        with closing(connect(config.database, readonly=True)) as db:
            assert db.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
            assert [tuple(row)[:-1] for row in db.execute("SELECT * FROM chunks WHERE source_type='pdf'")] == other
            assert any(h.get('table_provenance') for h in SQLiteSearch(db).search_fulltext('RecQ'))
        assert indexer.index_library(config)['files_extracted'] == 0
    assert all(p.read_bytes() == before[p] for p in (bib, csv_path, pdf))


def test_header_policy_change_refreshes_only_tables_and_zip(tmp_path):
    table = tmp_path / 'table.csv'
    table.write_text('RecQ,42\nOther,10\n')
    paper = tmp_path / 'paper.pdf'
    paper.write_bytes(synthetic_pdf())
    archive = tmp_path / 'tables.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.write(table, 'table.csv')
    bib = tmp_path / 'refs.bib'
    bib.write_text('@article{A,title={Paper},Bdsk-File-1={table.csv},'
                   'Bdsk-File-2={paper.pdf},Bdsk-File-3={tables.zip}}')
    config = Config(bib, tmp_path / 'db.sqlite3')
    indexer.index_library(config)
    config = replace(config, extraction=replace(config.extraction, table_header_rows=0))
    report = indexer.index_library(config)
    assert report['files_extracted'] == 2 and report['files_reused'] == 1
    with closing(connect(config.database, readonly=True)) as db:
        hit = next(h for h in SQLiteSearch(db).search_fulltext('RecQ') if h['source_type'] == 'csv')
        assert hit['row_start'] == 1 and hit['table_provenance']['header_status'] == 'none'
    assert indexer.index_library(config)['files_extracted'] == 0
