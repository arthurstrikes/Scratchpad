# Fixtures

Synthetic IPOWatch-shaped HTML used by tests and by `--fixture-dir` dry runs.

**These contain invented numbers.** They are not scraped from IPOWatch and
must never be treated as market data. They exist to exercise the parser
(header matching, SME detection via name / URL / section heading, QIB+NII
exclusion, date-range splitting, ₹0 GMP) without network access.

Once a live run succeeds, drop a real snapshot from `output/snapshots/` in
here to pin the parser against IPOWatch's actual markup.
