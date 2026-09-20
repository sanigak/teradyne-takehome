import re

from .models import Routing
from .retrieval import STOPWORDS

METADATA = re.compile(r"^(?:[A-Z]{1,3}\d+:\s*)?(?:Title|Date|Author|Attendees|Client|Domain|Priority|Classification)\s*:", re.I)


def words(text):
    return {word for word in re.findall(r"\w+", text.casefold()) if len(word) > 2 and word not in STOPWORDS}


def responsibility(line, name):
    """Rank only explicit source statements; never introduce inferred identities."""
    if line.casefold().startswith(name.casefold() + ":") and re.search(r"\bI (?:own|am responsible|coordinate|will resolve)\b|\b(?:route|routed) to me\b", line, re.I):
        return True
    escaped = re.escape(name)
    return bool(re.search(escaped + r"\s+(?:owns?|coordinates?|leads?|is responsible|will resolve|must resolve)\b", line, re.I)
                or re.search(r"\b(?:owner|contact|route to|routed to)\s*:?\s*" + escaped + r"\b", line, re.I))


def build_routing(question, evidence):
    terms = words(question)
    recipients = {}
    for item in evidence:
        names = list(dict.fromkeys(([item.author] if item.author else []) + item.attendees))
        body = [line.strip() for line in item.text.splitlines() if line.strip()
                and not METADATA.match(line.strip())
                and line.strip().lstrip("# ").casefold() != item.title.casefold()]
        if not body:
            continue
        has_term_overlap = any(terms & words(line) for line in body)
        for name in names:
            if not name or name.casefold() in {"unknown", "unknown author", "n/a", "none"}:
                continue
            candidates = []
            for line in body:
                overlap = len(terms & words(line))
                owns = responsibility(line, name) and (overlap > 0 or not has_term_overlap)
                candidates.append(((int(owns), overlap, int(name.casefold() in line.casefold()), len(line)), line))
            score, excerpt = max(candidates, key=lambda candidate: candidate[0])
            entry = recipients.setdefault(name, {"items": [], "score": (-1, -1, -1, -1), "excerpt": "", "source": None})
            entry["items"].append(item)
            if score > entry["score"]:
                entry.update(score=score, excerpt=excerpt, source=item)
    ranked = sorted(recipients.items(), key=lambda pair: (*pair[1]["score"][:3], len({item.document_id for item in pair[1]["items"]})), reverse=True)
    routing = []
    for recipient, entry in ranked[:3]:
        source = entry["source"]
        excerpt = entry["excerpt"]
        if len(excerpt) > 600:
            anchor = excerpt.casefold().find(recipient.casefold())
            start = max(0, anchor - 80) if anchor >= 0 else 0
            excerpt = ("…" if start else "") + excerpt[start:start + 600] + "…"
        label = "Named responsibility" if entry["score"][0] else "Author or attendee; relevant source content"
        routing.append(Routing(recipient=recipient, reason=f"{label} in {source.filename}: {excerpt}",
            draft_question=f"Hi {recipient},\n\nCould you clarify the following question?\n\n{question}\n\nThe current knowledge sources do not fully establish the answer. Please share the decision or source of truth.\n\nThank you.",
            evidence_ids=list(dict.fromkeys(item.chunk_id for item in entry["items"]))))
    return routing
