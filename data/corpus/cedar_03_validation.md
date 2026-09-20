# Cedar Vale — validation and privacy decision

Date: 2026-09-13
Author: Nina Shah
Attendees: Nina Shah; Ines Duarte; Elliot Reed; Oscar Bell
Client: Cedar Vale
Domain: Evaluation and privacy
Priority: High
Classification: SYNTHETIC — fictional evaluation material

Transcript — edited for clarity; all people and engagements are fictional.

Elliot Reed: The frozen policy test set contains 80 questions: 60 answerable policy questions, 12 deliberately missing policies, and 8 cross-clinic access attempts. We scored claim support separately from retrieval coverage.

Nina Shah: Decision: delete raw user prompts within 24 hours. This supersedes the seven-day proposal in the September 5 privacy review. Keep only redacted operational counters for 30 days; no patient identifiers belong in analytics.

Ines Duarte: To confirm, the seven-day period was a draft, not an active production policy. Nina owns this final privacy decision and Oscar will implement the scheduled deletion.

Oscar Bell: I will add deletion job monitoring and verify a record older than 24 hours cannot be retrieved from the raw-prompt store. This retention rule is separate from the signed source-policy documents.

Elliot Reed: Acceptance requires zero cross-clinic disclosures, at least 95 percent supported claims on answerable questions, and routing for deliberately absent policies. The score workbook records observed results and remaining review items.

Nina Shah: Open issue: paid parental leave eligibility for temporary contractors is not defined in our approved handbook extracts. Route that policy question to me rather than borrowing rules from another employer.
