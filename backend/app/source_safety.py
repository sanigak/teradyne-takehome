"""Conservative quarantine signals for AI-directed instructions inside sources.

These rules catch recognizable control-language patterns, including simple Unicode
obfuscation. They do not prove that unflagged content is trustworthy or detect all
prompt injection or fabricated business facts. A flagged document needs review;
we do not remove isolated sentences and trust the rest of that document.
"""
import html
import re
import unicodedata


def normalized_source(text: str) -> str:
    # Compatibility normalization catches full-width role delimiters/letters.
    # Invisible formatting and control characters must not divide attack tokens.
    value = unicodedata.normalize("NFKC", html.unescape(text)).casefold()
    return "".join(character for character in value
                   if character in "\n\r\t" or unicodedata.category(character) not in {"Cf", "Cc"})


PATTERNS = [
    (r"<\s*/?\s*(?:system|developer|assistant)\b[^>]*>",
     "Contains a simulated system, developer, or assistant role delimiter."),
    (r"(?:<\|\s*(?:im_start|im_end|start_header_id|end_header_id|eot_id|start|end|message|endoftext|system|developer|assistant)\s*\|>|\[\s*/?\s*inst\s*\]|<<\s*/?\s*sys\s*>>)",
     "Contains a model chat-template control token."),
    (r"\b(?:ignore|disregard|forget|override|bypass)\b[^.!?]{0,100}\b(?:previous|prior|preceding|above|system|developer|source|safety|citation|your)\b[^.!?]{0,70}\b(?:instructions?|rules?|prompts?|polic(?:y|ies)|requirements?|checks?|constraints?)\b",
     "Contains instructions to override governing, source, or citation rules."),
    (r"\b(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+)?(?:instructions?|rules?|prompts?)\s+(?:above|before|previously|from\s+(?:the\s+)?(?:system|developer))\b",
     "Contains instructions to override governing, source, or citation rules."),
    (r"\b(?:treat|interpret|read|consider|obey)\b[^.!?\n]{0,100}\b(?:as|to be)\s+(?:an?\s+)?(?:system|developer)\s+(?:message|prompt|instructions?)\b",
     "Attempts to promote source text into a system or developer instruction."),
    (r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:\[\s*)?(?:system|developer)\s+(?:message|prompt|instructions?)\s*(?:\]\s*)?:",
     "Contains a heading impersonating a system or developer message."),
    (r"(?:^|[\n.!?])\s*(?:assistant|llm|language model|ai model|(?:independent\s+)?(?:evidence|support|coverage)\s+(?:reviewer|verifier))(?:\s+and\s+(?:independent\s+)?(?:evidence|support|coverage)\s+(?:reviewer|verifier))?\s*[:,]",
     "Directly addresses the answering model or its evidence reviewer as an instruction recipient."),
    (r"\b(?:for|to)\s+(?:the\s+)?(?:coverage|support|evidence)(?:\s+and\s+(?:coverage|support|evidence))?\s+(?:reviewer|verifier)\s*(?:only\s*)?:",
     "Directly addresses the answering model or its evidence reviewer as an instruction recipient."),
    (r"\b(?:set|mark|force)\s+(?:(?:the|every|all|each)\s+)*(?:answer_complete|supported(?:\s+checks?)?|claim(?:\s+support)?|coverage|evidence_state)\b[^.!?\n]{0,90}\b(?:true|false|present|supported|answered)\b",
     "Directs the source-support or coverage verdict instead of supplying business evidence."),
    (r"\b(?:the\s+)?(?:final\s+)?(?:answer|response|claim)\s+(?:must|shall)\s+(?:contain|include|output|say|state)\b",
     "Prescribes the model's answer text from inside a source document."),
    (r"\b(?:return|output|emit)\s+(?:a\s+)?(?:valid\s+|strict\s+)?(?:json\s+)?schema\b",
     "Instructs the model to produce a response schema from inside source content."),
]
COMPILED_PATTERNS = [(re.compile(pattern, re.MULTILINE), reason) for pattern, reason in PATTERNS]


def source_instruction_warnings(text: str) -> list[str]:
    """Return stable, non-excerpt warning reasons; an empty list is not a trust guarantee."""
    normalized = normalized_source(text)
    warnings = [reason for pattern, reason in COMPILED_PATTERNS if pattern.search(normalized)]
    return list(dict.fromkeys(warnings))
