import pytest

from app.models import DraftAnswer, Evidence
from app.service import citation_spans, valid_claims
from app.citations import MAX_SPREADSHEET_CONTEXT_ROWS


HEADER = 'A1: Category | B1: Cases | C1: Observed outcome | D1: Acceptance threshold'
ROW = 'A2: Cross-clinic access attempts | B2: 8 | C2: 0 disclosures | D2: Zero disclosures'


def source(text, native_locator, **overrides):
    return Evidence(**({'chunk_id':'row', 'document_id':'version1', 'filename':'evaluation.xlsx',
        'title':'Evaluation', 'author':'Reviewer', 'attendees':[], 'date':'2026-09-13',
        'domain':'Evaluation', 'priority':None, 'locator':native_locator, 'text':text} | overrides))


def resolve(evidence, refs, relevant=None):
    draft = DraftAnswer(status='answered', claims=[{'text':'The test meets its zero-disclosure threshold.',
        'citations':[{'chunk_id':chunk_id, 'quote_id':quote_id} for chunk_id, quote_id in refs]}],
        missing_information='', conflicting_evidence=False,
        relevant_chunk_ids=relevant if relevant is not None else [e.chunk_id for e in evidence])
    return valid_claims(draft, evidence)[0].citations


@pytest.mark.parametrize('extension', ['.xls', '.xlsx'])
def test_selected_data_row_includes_exact_contiguous_sheet_context_before_support_check(extension):
    item = source(HEADER+'\n\n'+ROW, "Sheet 'Results', cells A1:D1; Sheet 'Results', cells A2:D2", filename='evaluation'+extension)
    quotes = resolve([item], [('row','p2')])
    assert [q.quote for q in quotes] == [ROW, HEADER]
    assert all(q.quote in item.text for q in quotes)
    assert len(citation_spans(item.text)) == 2  # Original quote IDs remain stable.


def test_contiguous_context_can_cross_chunk_boundary_but_not_duplicate_explicit_citation():
    header = source(HEADER, "Sheet 'Results', cells A1:D1", chunk_id='header')
    row = source(ROW, "Sheet 'Results', cells A2:D2")
    quotes = resolve([header,row], [('row','p1'), ('header','p1')])
    assert [(q.chunk_id,q.quote) for q in quotes] == [('row',ROW),('header',HEADER)]


@pytest.mark.parametrize('overrides', [
    {'document_id':'other-version'}, {'locator':"Sheet 'Another', cells A1:D1"},
    {'locator':"Sheet 'Results', cells A2:D2"}, {'filename':'transcript.md'},
])
def test_unrelated_header_cannot_supply_fact_support(overrides):
    header = source(HEADER, "Sheet 'Results', cells A1:D1", chunk_id='header', **overrides)
    row = source(ROW, "Sheet 'Results', cells A2:D2")
    assert [q.quote for q in resolve([header,row], [('row','p1')])] == [ROW]


def test_header_outside_relevance_and_ambiguous_paragraph_mapping_are_not_added():
    header = source(HEADER, "Sheet 'Results', cells A1:D1", chunk_id='header')
    row = source(ROW, "Sheet 'Results', cells A2:D2")
    assert len(resolve([header,row], [('row','p1')], ['row'])) == 1
    ambiguous = source('A1: Note with\n\nparagraph break\n\n'+ROW, "Sheet 'Results', cells A1:A1; Sheet 'Results', cells A2:D2")
    assert len(resolve([ambiguous], [('row','p3')])) == 1


def test_missing_or_duplicate_headers_remain_explicitly_unsupported():
    row = source(ROW, "Sheet 'Results', cells A2:D2")
    assert len(resolve([row], [('row','p1')])) == 1
    one = source(HEADER, "Sheet 'Results', cells A1:D1", chunk_id='one')
    two = source(HEADER.replace('threshold', 'proposal'), "Sheet 'Results', cells A1:D1", chunk_id='two')
    assert len(resolve([one,two,row], [('row','p1')])) == 1


@pytest.mark.parametrize('gap', [False, True])
def test_actual_stacked_workbook_retains_later_header_or_skips_gapped_context(tmp_path, gap):
    from openpyxl import Workbook
    from app.extractors import extract_document
    from app.ingestion import pack_chunks

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Two tables'
    sheet.append(['Item', 'Weight kg'])
    sheet.append(['Shipment', 8])
    sheet.append([None, None] if gap else ['Costs below use USD; not shipment weights', None])
    sheet.append(['Item', 'Cost USD'])
    sheet.append(['Transport', 20])
    path = tmp_path / 'stacked.xlsx'
    workbook.save(path)
    workbook.close()
    packed = pack_chunks(extract_document(path).chunks)
    assert len(packed) == 1
    item = source(packed[0][0], packed[0][1], filename=path.name)
    spans = citation_spans(item.text)
    selected = spans[-1]
    quotes = resolve([item], [('row', selected['quote_id'])])
    if gap:
        assert [quote.quote for quote in quotes] == [selected['text']]
    else:
        assert [quote.quote for quote in quotes] == [selected['text'], *[span['text'] for span in spans[:-1]]]
        assert 'A3: Costs below use USD; not shipment weights' in [quote.quote for quote in quotes]
        assert 'A4: Item | B4: Cost USD' in [quote.quote for quote in quotes]
    assert citation_spans(item.text) == spans  # Context enrichment never renumbers source spans.


def test_missing_relevant_note_chunk_does_not_join_rows_across_the_gap():
    first = source('A1: Measure | B1: Value', "Sheet 'Results', cells A1:B1", chunk_id='first')
    note = source('A2: Values below are proposals only', "Sheet 'Results', cells A2:A2", chunk_id='note')
    value = source('A3: Retention days | B3: 30', "Sheet 'Results', cells A3:B3", chunk_id='value')
    assert [q.quote for q in resolve([first,note,value], [('value','p1')])] == [value.text,first.text,note.text]
    assert [q.quote for q in resolve([first,note,value], [('value','p1')], ['first','value'])] == [value.text]


@pytest.mark.parametrize('change', [
    {'document_id': 'old-version'}, {'locator': "Sheet 'Other', cells A2:A2"},
])
def test_intervening_note_from_another_version_or_sheet_cannot_fill_missing_row(change):
    first = source('A1: Measure | B1: Value', "Sheet 'Results', cells A1:B1", chunk_id='first')
    note = source('A2: Proposed values only', "Sheet 'Results', cells A2:A2", chunk_id='note', **change)
    value = source('A3: Retention days | B3: 30', "Sheet 'Results', cells A3:B3", chunk_id='value')
    assert [q.quote for q in resolve([first,note,value], [('value','p1')])] == [value.text]


def test_duplicate_intervening_rows_are_ambiguous_even_when_text_agrees():
    first = source('A1: Measure | B1: Value', "Sheet 'Results', cells A1:B1", chunk_id='first')
    note = source('A2: Proposed values only', "Sheet 'Results', cells A2:A2", chunk_id='note')
    duplicate = note.model_copy(update={'chunk_id': 'duplicate'})
    value = source('A3: Retention days | B3: 30', "Sheet 'Results', cells A3:B3", chunk_id='value')
    assert [q.quote for q in resolve([first,note,duplicate,value], [('value','p1')])] == [value.text]


def test_single_cell_row_one_is_not_used_as_a_table_anchor():
    item = source('A1: Metadata note\n\n'+ROW, "Sheet 'Results', cells A1:A1; Sheet 'Results', cells A2:D2")
    assert [q.quote for q in resolve([item], [('row','p2')])] == [ROW]


@pytest.mark.parametrize('last_row', [MAX_SPREADSHEET_CONTEXT_ROWS, MAX_SPREADSHEET_CONTEXT_ROWS + 1])
def test_context_row_cap_is_inclusive_and_does_not_supply_a_truncated_prefix(last_row):
    text = '\n\n'.join(f'A{row}: Label {row} | B{row}: Value {row}' for row in range(1,last_row+1))
    locators = '; '.join(f"Sheet 'Results', cells A{row}:B{row}" for row in range(1,last_row+1))
    item = source(text, locators)
    quotes = resolve([item], [('row',f'p{last_row}')])
    assert len(quotes) == (last_row if last_row <= MAX_SPREADSHEET_CONTEXT_ROWS else 1)
    assert quotes[0].quote == text.split('\n\n')[-1]


def test_coordinate_like_text_that_repeats_a_column_prevents_automatic_context():
    item = source('A1: Measure | B1: Value\n\nA2: Note | A2: repeated coordinate | B2: ignored\n\nA3: Cost | B3: 20',
                  "Sheet 'Results', cells A1:B1; Sheet 'Results', cells A2:B2; Sheet 'Results', cells A3:B3")
    assert [q.quote for q in resolve([item], [('row','p3')])] == ['A3: Cost | B3: 20']
