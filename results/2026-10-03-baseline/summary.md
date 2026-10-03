# Eval run: 2026-10-03-baseline

53 cases · agent fingerprint(s) 5a7b8d8b9395ee04, 5a7b8d8b9395ee04, c01431cee64a7e2f, c01431cee64a7e2f, c01431cee64a7e2f · 2026-10-03T21:50:45+00:00

| variant | model | skills | context | accuracy (95% CI) | routing | escalation | priority | tokens/task | $/task | p50 latency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1-inline-haiku | claude-haiku-4-5-20251001 | skills_v1 | inline_all | 86.8% (75-93) | 100.0% | 94.2% | 87.0% | 26,468 | $0.0292 | 8.7s | 0 |
| v1-progressive-haiku | claude-haiku-4-5-20251001 | skills_v1 | progressive | 88.7% (77-95) | 100.0% | 94.2% | 91.3% | 10,154 | $0.0131 | 9.5s | 0 |
| v2-inline-haiku | claude-haiku-4-5-20251001 | skills | inline_all | 88.7% (77-95) | 98.1% | 92.3% | 93.5% | 13,252 | $0.0161 | 9.3s | 0 |
| v2-progressive-haiku | claude-haiku-4-5-20251001 | skills | progressive | 92.5% (82-97) | 96.2% | 94.2% | 95.7% | 7,400 | $0.0102 | 9.2s | 0 |
| v2-progressive-sonnet | claude-sonnet-5-5 | skills | progressive | 0.0% (-0-7) | - | - | - | 0 | $0.0000 | 0.0s | 53 |


**v1-inline-haiku** failed: bill-03, bill-05, bill-07, bill-09, bug-09, bug-11, bug-14


**v1-progressive-haiku** failed: bill-06, bill-07, bill-09, bill-12, bug-09, bug-10


**v2-inline-haiku** failed: bill-04, bill-07, bill-13, bug-08, bug-09, bug-10


**v2-progressive-haiku** failed: bill-13, bill-16, bug-09, bug-10


**v2-progressive-sonnet** failed: acct-01, acct-02, acct-03, acct-04, acct-05, acct-06, acct-07, acct-08, acct-09, acct-10, acct-11, acct-12, acct-13, acct-14, bill-01, bill-02, bill-03, bill-04, bill-05, bill-06, bill-07, bill-08, bill-09, bill-10, bill-11, bill-12, bill-13, bill-14, bill-15, bill-16, bug-01, bug-02, bug-03, bug-04, bug-05, bug-06, bug-07, bug-08, bug-09, bug-10, bug-11, bug-12, bug-13, bug-14, gen-01, gen-02, gen-03, gen-04, gen-05, gen-06, multi-01, multi-02, multi-03
