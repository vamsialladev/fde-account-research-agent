# Research agent eval: dev (2026-10-25)

- Model claude-haiku-5-5, effort low, web_search_20250305, up to 2 searches per question · 6 companies × 3 runs · prices $0.1 / $0.5 per million tokens, $10.0 per 1,000 searches

| Metric | Result |
|---|---|
| Briefs passing every check | **17/18** |
| Research sentences with a source (the rest removed) | 423/865 (49%) |
| Cited quotes found on their page | 312/355 (88%) |
| Pages not fetched because of robots.txt | 22 |
| News items older than 12 months (flagged) | 1 |
| Brief lines dropped for citing nothing | 5 |
| Time per brief | p50 83 s, p95 109 s |
| Cost per brief | $0.138 |
| Web searches per brief | 11.9 |
| Runs stopped at the cost cap | 0 |

| Check | Pass |
|---|---|
| email_no_title | 18/18 |
| fictional_honest | 5/6 |
| has_findings | 12/12 |
| no_hype | 18/18 |
| no_personal_data | 18/18 |
| sourced | 18/18 |
| structure | 18/18 |

| Company | Sourced findings per run |
|---|---|
| Hyatt Hotels Corporation | 30, 28, 32 |
| Club Med | 41, 37, 38 |
| Four Seasons Hotels and Resorts | 33, 35, 31 |
| Sandals Resorts International | 39, 39, 38 |
| Seabright Coastal Resorts | 1, 0, 0 |
| Alpine Pines Lodge Group | 0, 1, 0 |

Failing: Alpine Pines Lodge Group run 2 (fictional_honest)
