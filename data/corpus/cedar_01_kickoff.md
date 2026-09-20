# Cedar Vale — policy assistant kickoff

Date: 2026-09-03
Author: Ines Duarte
Attendees: Ines Duarte; Oscar Bell; Nina Shah; Elliot Reed
Client: Cedar Vale
Domain: Product and privacy
Priority: High
Classification: SYNTHETIC — fictional evaluation material

Transcript — edited for clarity; all people and engagements are fictional.

Ines Duarte: Cedar Vale is piloting an internal policy-search assistant for clinic administrators. It answers questions about staff policies and cites the approved handbook. It must not diagnose patients or recommend treatment.

Nina Shah: I own policy content approval. Staff may paste accidental patient identifiers into questions, so we need a clear input warning and reliable redaction. The corpus itself must exclude patient records.

Oscar Bell: I own access-control implementation. Each chunk will carry the clinic and policy access group. Filtering occurs before model context assembly, not after an answer is generated.

Elliot Reed: I own evaluation and incident triage. We should test one user's inability to see another clinic's restricted policies and require citations on each policy claim.

Ines Duarte: Decision: pilot only with administrative users in East and Harbor clinics. Escalate missing policy answers to Nina; do not generate a substitute policy.

Nina Shah: Retention is still under review. The draft privacy review will propose a period, but no one should represent that draft as a final decision.
