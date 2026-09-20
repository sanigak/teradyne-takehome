# Cedar Vale — tenant isolation review

Date: 2026-09-08
Author: Oscar Bell
Attendees: Oscar Bell; Elliot Reed; Nina Shah
Client: Cedar Vale
Domain: Identity and access
Priority: Critical
Classification: SYNTHETIC — fictional evaluation material

Transcript — edited for clarity; all people and engagements are fictional.

Oscar Bell: Cedar now applies clinic_id and policy_group filters before retrieval ranking. Both claims must come from the authenticated identity token; the user cannot select an arbitrary clinic in a query parameter.

Elliot Reed: I tested an East-clinic user against Harbor-only policy text. The restricted chunks never reached model context. We also need a missing-claim test.

Oscar Bell: Decision: missing clinic or policy-group claims fail closed with a forbidden response. We do not fall back to a global collection. I own the middleware and the access regression tests.

Nina Shah: Policy publication remains a human approval process. A user correction goes into review, not directly into the policy corpus. Otherwise a well-intentioned correction could become an unapproved rule.

Elliot Reed: Action: I will add an identity-expiration case and a revoked-group case by September 12. Every evaluation record should keep the tested document version and retrieval evidence.

Oscar Bell: An on-call weekend rota is not documented yet. I can discuss access failures but cannot promise a staffed weekend response time.
