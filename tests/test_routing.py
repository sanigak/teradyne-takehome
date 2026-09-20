from app.models import Evidence
from app.routing import build_routing


def evidence(chunk_id, text, author="Noah Kim", attendees=None):
    return Evidence(chunk_id=chunk_id, document_id=chunk_id, filename=f"{chunk_id}.xlsx", title="Vendor review", author=author, attendees=attendees or ["Noah Kim", "Emma Laurent"], date="2026-09-01", domain="Vendor contracting", priority=None, locator="Sheet 'Review', cells A1:D10", text=text)


def test_explicit_owner_wins_over_frequency_with_real_body_excerpt():
    header = "Title: Vendor review\nDate: 2026-09-01\nAuthor: Noah Kim\nAttendees: Noah Kim; Emma Laurent\n" + "Classification: Synthetic evaluation fixture metadata\n" * 8
    body = "Emma Laurent: I own the weather vendor contract request. The signed deletion SLA is still unknown."
    sources = [evidence("register", header + body)]
    sources.extend(evidence(f"notes{i}", "The weather vendor signed deletion SLA remains outstanding.", attendees=["Noah Kim"]) for i in range(3))
    routes = build_routing("What is the weather vendor's signed deletion SLA?", sources)
    assert routes[0].recipient == "Emma Laurent"
    assert body in routes[0].reason
    assert "Classification:" not in routes[0].reason
    assert routes[0].evidence_ids == ["register"]


def test_body_mention_does_not_invent_a_recipient_outside_attribution():
    sources = [evidence("register", "Unlisted Person owns the vendor deletion agreement.", attendees=["Noah Kim"])]
    routes = build_routing("Who owns the vendor deletion agreement?", sources)
    assert all(route.recipient == "Noah Kim" for route in routes)


def test_metadata_only_source_does_not_supply_a_supporting_body_excerpt():
    source = evidence("register", "Title: Vendor review\nAuthor: Noah Kim\nDate: 2026-09-01\nDomain: Vendor deletion SLA")
    assert build_routing("What is the vendor deletion SLA?", [source]) == []
