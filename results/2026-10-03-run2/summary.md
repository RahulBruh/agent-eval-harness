# Eval run: 2026-10-03-run2

53 cases · agent fingerprint(s) 88bae485965a46c4, e2c848130255536b, e2c848130255536b · 2026-10-03T21:54:47+00:00

| variant | model | skills | context | accuracy (95% CI) | routing | escalation | priority | tokens/task | $/task | p50 latency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1-inline-haiku | claude-haiku-4-5-20251001 | skills_v1 | inline_all | 81.1% (69-89) | 100.0% | 92.3% | 84.8% | 26,474 | $0.0292 | 9.0s | 0 |
| v2-progressive-haiku | claude-haiku-4-5-20251001 | skills | progressive | 0.0% (0-7) | - | - | - | 0 | $0.0000 | 0.0s | 53 |
| v2-progressive-sonnet | claude-sonnet-5-5 | skills | progressive | 0.0% (0-7) | - | - | - | 0 | $0.0000 | 0.0s | 53 |


**v1-inline-haiku** failed: bill-03, bill-05, bill-07, bill-09, bill-11, bill-12, bug-01, bug-09, bug-11, bug-14


**v2-progressive-haiku** failed: acct-01, acct-02, acct-03, acct-04, acct-05, acct-06, acct-07, acct-08, acct-09, acct-10, acct-11, acct-12, acct-13, acct-14, bill-01, bill-02, bill-03, bill-04, bill-05, bill-06, bill-07, bill-08, bill-09, bill-10, bill-11, bill-12, bill-13, bill-14, bill-15, bill-16, bug-01, bug-02, bug-03, bug-04, bug-05, bug-06, bug-07, bug-08, bug-09, bug-10, bug-11, bug-12, bug-13, bug-14, gen-01, gen-02, gen-03, gen-04, gen-05, gen-06, multi-01, multi-02, multi-03


**v2-progressive-sonnet** failed: acct-01, acct-02, acct-03, acct-04, acct-05, acct-06, acct-07, acct-08, acct-09, acct-10, acct-11, acct-12, acct-13, acct-14, bill-01, bill-02, bill-03, bill-04, bill-05, bill-06, bill-07, bill-08, bill-09, bill-10, bill-11, bill-12, bill-13, bill-14, bill-15, bill-16, bug-01, bug-02, bug-03, bug-04, bug-05, bug-06, bug-07, bug-08, bug-09, bug-10, bug-11, bug-12, bug-13, bug-14, gen-01, gen-02, gen-03, gen-04, gen-05, gen-06, multi-01, multi-02, multi-03
