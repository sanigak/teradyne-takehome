"""Resolve bounded native source context without inventing quotations."""
import re

MAX_SPREADSHEET_CONTEXT_ROWS = 20
MAX_TITLE_CONTEXT_CHARACTERS = 300


def source_title_context_citations(evidence, spans, relevant):
    """Return an exact source-start title for each relevant immutable chunk.

    A title in metadata alone is not a quotation. Require one unambiguous native
    first-line/shape anchor, its whole single-line source paragraph,
    and an exact title match after removing only a format's visible title label.
    Never search body substrings or use another document version's heading.
    Word paragraph numbers exclude preceding tables, and spreadsheet locators
    lack workbook sheet order. Neither proves a document-start title; explicit
    citations still work, and spreadsheet row context is resolved separately.
    """
    documents = {}
    for item in evidence:
        documents.setdefault(item.document_id, []).append(item)
    result = {}
    for items in documents.values():
        # Inconsistent immutable-source metadata is ambiguous, even if only
        # one of the inconsistent chunks was declared relevant by the model.
        if len({(item.filename, item.title) for item in items}) != 1:
            continue
        filename = items[0].filename.lower()
        if filename.endswith(".md"):
            native_start, label = "Lines 1-1", "# "
        elif filename.endswith((".ppt", ".pptx")):
            native_start, label = "Slide 1, shape 1", None
        else:
            continue
        anchors = [(item, index) for item in items
                   for index, locator in enumerate(item.locator.split("; ")) if locator == native_start]
        # Duplicate native starts remain ambiguous even when their text agrees.
        if len(anchors) != 1:
            continue
        item, index = anchors[0]
        if item.chunk_id not in relevant or index != 0:
            continue
        paragraphs = list(spans[item.chunk_id].values())
        if not paragraphs or len(paragraphs) != len(item.locator.split("; ")):
            continue
        quote = paragraphs[0]
        if len(quote) > MAX_TITLE_CONTEXT_CHARACTERS or "\n" in quote or "\r" in quote:
            continue
        if label:
            if not quote.startswith(label):
                continue
            title = quote[len(label):]
        else:
            title = quote.removeprefix("Title: ")
        if not title.strip() or " ".join(title.split()) != " ".join(item.title.split()):
            continue
        for target in items:
            if target.chunk_id in relevant:
                result[target.chunk_id] = {"chunk_id": item.chunk_id, "quote": quote}
    return result


def spreadsheet_rows(evidence, spans):
    if not evidence.filename.lower().endswith((".xls", ".xlsx")):
        return []
    locators = evidence.locator.split("; ")
    paragraphs = list(spans.items())
    # A cell containing paragraph breaks cannot be paired unambiguously with
    # packed locators. Keep explicit model-selected citations in that case.
    if len(locators) != len(paragraphs):
        return []
    rows = []
    for locator, (quote_id, text) in zip(locators, paragraphs):
        match = re.fullmatch(r"Sheet '(.+)', cells ([A-Z]{1,3})([1-9][0-9]{0,6}):([A-Z]{1,3})([1-9][0-9]{0,6})", locator)
        if not match or match[3] != match[5]:
            continue
        cells = re.findall(r"(?:^| \| )([A-Z]{1,3})([1-9][0-9]{0,6}): ", text)
        columns = [sum((ord(char) - 64) * 26 ** index for index, char in enumerate(reversed(column))) for column, _ in cells]
        if (not cells or cells[0] != (match[2], match[3])
                or cells[-1] != (match[4], match[5]) or any(row != match[3] for _, row in cells)):
            continue
        # Embedded coordinate-looking cell text must not create duplicate or
        # out-of-order columns that masquerade as native cell boundaries.
        if columns != sorted(set(columns)):
            continue
        rows.append({"sheet": match[1], "row": int(match[3]),
                     "columns": {column for column, _ in cells}, "quote_id": quote_id, "text": text})
    return rows


def spreadsheet_context_citations(evidence, spans, relevant):
    """Supply bounded preceding rows, without guessing which row is a header.

    The same immutable sheet must have a unique, contiguous native row mapping
    from multi-column row 1 through the selected row. Include every intervening
    row, including notes and later table headers. Missing or ambiguous ranges
    receive no automatic context; explicitly selected citations remain intact.
    """
    rows, sheets = {}, {}
    for item in evidence:
        if item.chunk_id not in relevant:
            continue
        for row in spreadsheet_rows(item, spans[item.chunk_id]):
            key = (item.document_id, row["sheet"])
            rows[(item.chunk_id, row["quote_id"])] = (key, row)
            sheets.setdefault(key, {}).setdefault(row["row"], []).append((item.chunk_id, row))
    result = {}
    for reference, (key, row) in rows.items():
        if not 1 < row["row"] <= MAX_SPREADSHEET_CONTEXT_ROWS:
            continue
        preceding = [sheets[key].get(number, []) for number in range(1, row["row"] + 1)]
        if any(len(candidates) != 1 for candidates in preceding):
            continue
        if len(preceding[0][0][1]["columns"]) < 2:
            continue
        result[reference] = [{"chunk_id": candidates[0][0], "quote": candidates[0][1]["text"]}
                             for candidates in preceding[:-1]]
    return result
