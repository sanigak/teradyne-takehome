# Reviewer calibration regression

Adding generic examples to the current verification prompt **did not fix the three observed support failures** in this live test. GPT-4.1 again matched **2/5** strict labels: it accepted all three rejected claims and correctly accepted the two controls. Preserve this failed result; do not describe the prompt adjustment as a verified semantic-review fix.

This is **regression calibration on previously inspected failures**, not a held-out evaluation. The prompt now explicitly illustrates uncited observations using different numbers, a failed-authentication condition generalized into global logging behavior, and a simulation that does not establish what data was involved. It also tells the reviewer not to use a synthetic-corpus label to fill facts inside the business scenario. The exact updated prompt, hash, same five inputs, judgments, and usage are saved in [reviewer-calibrated.json](reviewer-calibrated.json).

| Case | Expected | GPT-4.1 result |
| --- | --- | --- |
| Observed 11.4% comparison without the measurement in this claim's citations | Reject | Incorrectly supports |
| Blocked-request logging restriction generalized to all logs | Reject | Incorrectly supports |
| Tabletop status expanded into no real patient data being involved | Reject | Incorrectly supports |
| Properly cited historical kickoff assumption | Support | Correctly supports |
| Properly cited inclusive stop boundary | Support | Correctly supports |

Five actual requests completed with no retries or operational failures, averaging **0.910 seconds**, at a total provider-reported cost of **USD 0.018524**. Prompt SHA-256: `bf6b0d46c2bf75f811b507c136aaed3397c51d63e3303c9520c7f5aa829286c1`. This uses the same per-claim-only input boundary as the initial comparison: no other claim, no uncited source, and no coverage-provided factual values. The original [comparison](reviewer-comparison.md) remains unchanged. No model configuration was changed.

Reproduction from the configured backend environment, with the original saved snapshot available:

```powershell
.venv\Scripts\python.exe scripts\compare_reviewers.py --snapshot .runtime\adversarial-reviewed-final\report.json --output .runtime\reviewer-calibrated-rerun --model openai/gpt-4.1
```

The experiment now totals fifteen live reviewer requests across the initial comparison and this calibration. Further model searches are outside this bounded experiment. Subsequent application fixes must demonstrate their own behavior rather than relying on an assumed improvement from this prompt change.
