# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.1.0] - 2026-10-25
### Added
- Three example briefs anyone can open for free (`data/examples/`, copied unchanged from the saved eval run by
  `scripts/make_examples.py`); live runs need `DEMO_CODE` or are limited to 3 a day; monthly cost cap read from the
  durable ops log (decision 10).
- Shared guardrails, tracing and ops log from [hotel-ai-platform](https://github.com/vamsialladev/hotel-ai-platform)
  v0.1.3 (decision 11): input check on company names and chat questions, every pipeline step a span with its cost,
  "Reference: ..." on errors, hidden Admin page, JSON startup logs, privacy note, `?source=keepawake` runs nothing.
- The critic removes planted instructions from findings.
- Red-team suite in CI (`scripts/run_redteam.py`, docs/RED_TEAM.md) and a CycloneDX SBOM artifact.

## [1.0.0] - 2026-10-25

### Added

- Four-step research pipeline: planner, researchers (Claude Haiku 5.5 with Anthropic web search, at most 2 searches
  per question), a critic in plain code (sources, personal data, stale news, quote re-checked on its page) and a
  writer that may only cite kept findings.
- A polite fetcher: robots.txt first, a named user agent, a cache, size and time limits.
- A cost cap per run ($0.25), 3 briefs per visit, 30 briefs and $3 per day.
- Streamlit app: live step status, the brief with numbered sources, the steps with time and cost, a chat about the
  brief (BM25 over its findings, follow-ups rewritten, no new searches) and a read-only share link.
- Eval: 6 dev companies (2 fictional) and 2 held-out (1 fictional), 3 runs, deterministic checks, re-scoring and a
  labelling sample; a CI gate that re-scores the saved runs.
- Business case calculator (`scripts/business_case.py --scenarios`), decisions 1–8, architecture, security with
  the OWASP LLM Top 10.

### Fixed (found in the pilot run, before the final eval)

- The outreach email described the sender with a job title. It no longer describes the sender, and a new check
  fails any email that does (decision 8).
- Briefs for fictional companies had no use-case hypotheses; they now get 3 marked "unknown".
