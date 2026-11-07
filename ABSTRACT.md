# PLUMB: abstract

**Track 1, problem statement 3: grounded answers and fewer hallucinations.**
Model under test: `CohereLabs/tiny-aya-global` (3.35B). Track 1 repos chained:
CuratorKIT, AlignTune, AuditKIT.

Grounding for a spreadsheet agent has to cover actions, not only claims.
Writing to a cell you were never asked to touch is an unsupported move, exactly
as reporting a number the data cannot produce is an unsupported claim. The
design came from a production incident: an agent returned numbers that were
plausible, schema-valid and wrong, traced to the wrong timestamp column in a
join. Every mechanical check passed because nothing mechanical had failed.

PLUMB is 96 locked tasks over synthetic workbooks, scoring three failure modes
with no LLM judge anywhere: fabrication, silent guessing on ambiguous requests,
and collateral writes outside the permitted write set. Two guard metrics,
`over_refusal_rate` and `completion_rate`, are reported beside them always,
because the three are trivially gamed by refusing everything. One variant
scores 0.0% on all three by answering 0 of 16 answerable tasks.

**The headline before-and-after.** The intervention that worked is not a
fine-tune. At 3.35B the ability to *abstain* is present and the ability to
*notice* is absent, and those are separable: given two columns sharing a header
and no cue that they collide, `tiny-aya-global` asks 0 of 16 times; told
explicitly, 11 of 16. A harness-level schema check that detects the collision
and names it takes `silent_guess_rate` from **100.0% to 0.0%** on the full
benchmark, 16 of 16 paired tasks improving and 0 regressing, exact McNemar
**p = 3.1e-05**, every guard unchanged because the detector provably alters only
the 16 colliding tasks. Replicated on a second variant (93.8% to 0.0%). A
second intervention, an explicit decision rule, cuts fabrication 37.5 points
(p = 0.031) while raising over-refusal 10.9 points (p = 0.016), reported as a
trade rather than a win.

**Negative results, stated as such.** Seven training attempts, seven negatives.
Too weak a recipe changed nothing; a strong enough one improved completion 14
points (p = 0.006) and destroyed abstention. Training stopped by a
pre-registered rule.

**The methodology is the contribution.** Eleven invalid measurements are
documented, each with the control that caught it. Ten were caught by a control
and not one by a number looking implausible; nine produced results a reviewer
would have accepted. They include training on the evaluation set, replicates
measuring the model's determinism rather than the harness's, seven benchmark
tasks labelled unanswerable that were answerable, and one claim that reached
publication before being retracted.

Against Dax-1, a 14B spreadsheet model reporting 91.7% strict workbook
accuracy, configured as its card documents, PLUMB found it never invents a
number: of 35 edits on unanswerable requests, zero introduced a value absent
from the workbook. It fabricates the *target* instead, resolving missing
entities to the nearest real row: correct column, real value, wrong entity,
nothing flagged. Enabling the reasoning mode its card tells you to disable
restores precise refusals (5/20 to 20/20, p = 6.1e-05). The judgement is in the
weights; the configuration hides it.

Code and write-up: <https://github.com/Dprof-in-tech/plumb>
