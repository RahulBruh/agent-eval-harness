# Run 2 (partial)

The API account ran out of credits during this run. Only **v1-inline-haiku** completed
(53/53 cases). Every `v2-progressive-haiku` and `v2-progressive-sonnet` case errored with
`credit balance is too low`, so their rows here are not meaningful.

What this run does show: the v1-inline-haiku configuration (skills_v1 unchanged since run 1,
temperature 0) scored **81.1%** here vs **86.8%** in run 1. That is run-to-run variance
of about 3 cases out of 53, within both runs' 95% confidence intervals, and it's why single-run
accuracy differences of a few points shouldn't be read as real improvements.
