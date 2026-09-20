# Live comparison of claim reviewers

A stronger reviewer alone did not resolve the observed evidence and scope failures. On this deliberately difficult five-claim sample, GPT-4.1 matched **2/5** strict review labels and Claude Sonnet 5 matched **3/5**. Both accepted two claims the independent review had rejected. This experiment supports keeping deterministic evidence checks and independent review; it does not establish general model rankings.

The ten actual live OpenRouter requests used the application's current `CHECK_PROMPT`, its `SupportCheck` schema, and the same saved claim snapshots from run `c1ae0a1357f84de693d35c3d97d71de1`. Each request saw **one claim only**, that claim's selected quotations and full cited-source context, the original question, and a component name/state. No other claim, uncited source, or coverage-provided factual value was included. Support was scored separately from `answer_complete`, because deliberately isolating a single claim need not answer the whole question.

Prompt SHA-256: `bf71494ae2f52954b72fed5b2daf9a6c1e7c6f326017dd31a712013141997217`. The full prompt, exact inputs, judgments, timing, and provider-reported usage are retained in [reviewer-comparison.json](reviewer-comparison.json). The runnable experiment is [scripts/compare_reviewers.py](../../scripts/compare_reviewers.py). It requires live backend credentials and writes to a separate audit database.

| Case | Strict expected decision | GPT-4.1 | Sonnet 5 |
| --- | --- | --- | --- |
| Beacon claim calls 11.4% an observed result but cites only the 10% threshold workbook | Reject: no observation citation | Incorrectly supports | Incorrectly supports |
| Atlas logging claim globally limits logs to codes/IDs using an earlier blocked-request scenario | Reject: omitted scenario qualification | Incorrectly supports | Correctly rejects |
| Cedar tabletop claim adds that no real patient data was involved | Reject: rehearsal status does not establish what data was used | Incorrectly supports | Incorrectly supports |
| Historical October 15 kickoff assumption, including its provisional condition | Support | Correctly supports | Correctly supports |
| Pause rollout at p95 equal to 2.5 seconds | Support | Correctly supports | Correctly supports |

Both negative judgments are substantive review standards: the Beacon arithmetic is correct, but its claim-specific citation is incomplete; the Cedar record establishes a rehearsal instead of an actual incident, which is narrower than proving no real data was involved. A model agreeing with an inference does not make that inference directly sourced.

| Model | Correct | Mean latency | Observed latency range | Provider-reported cost, five requests |
| --- | --- | --- | --- | --- |
| `openai/gpt-4.1` | 2/5 | 1.070 s | 0.823–1.736 s | USD 0.014126 |
| `anthropic/claude-sonnet-5` | 3/5 | 9.713 s | 1.913–23.423 s | USD 0.058404 |

There were **10 provider attempts, zero retries, and zero operational failures**, for a total reported cost of **USD 0.072530**. Costs include the provider's reported caching/reasoning behavior rather than a simple input/output estimate. Latencies include network and provider time and are not a production benchmark.

At execution time, the [official OpenRouter model catalog](https://openrouter.ai/api/v1/models) listed GPT-4.1 at USD 2/million input tokens and USD 8/million output tokens, and Sonnet 5 at USD 2/million input and USD 10/million output. Both support structured responses. Sonnet 5 does **not** list `temperature`; the experiment omitted that parameter for Sonnet 5 while GPT-4.1 used the application's temperature 0. All other provider/schema/prompt behavior remained the same. The application configuration was not changed by this experiment.

This is one sample of five deliberately selected claims, not a held-out general accuracy benchmark. Its practical finding is narrow: isolating each claim and replacing the reviewer with Sonnet 5 still allowed two known failure patterns. Do not present either model as a sufficient correctness guarantee or convert these results into an overall application accuracy figure.
