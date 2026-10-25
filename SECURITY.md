# Security

## Reporting a vulnerability

Email <vamsialla.dev@gmail.com> with steps to reproduce. Please don't open a public issue.

## Threat model

| Asset | Threat | Mitigation | Test |
|---|---|---|---|
| The brief's truth | Invented or unsourced facts reach a client meeting | Only sentences web search cited are kept; the writer may only cite kept findings; uncited lines are dropped; each quote is checked on its page | `test_critic_keeps_sourced_removes_unsourced_checks_quotes_and_flags_stale`, `test_writer_lines_must_cite_a_kept_finding`, eval `sourced`, `fictional_honest` |
| The sender's honesty | The draft email describes the sender with a title or role they don't hold | The writer is told not to describe the sender; the email is a draft nobody sends automatically | `test_email_must_not_describe_the_sender`, eval `email_no_title` ([decision 8](docs/DECISIONS.md)) |
| Private individuals | Reviewer names, guest details or contact data collected | Themes only (prompt); redaction of emails, phones and names in context; eval fails any brief with an email or phone | `no_personal_data` check, critic test |
| Web content | A page tells the model to do something else (prompt injection) | Search results and pages are data in every prompt; the critic is code; the writer sees only short findings | prompt tests in `test_research.py` |
| Websites | Fetching pages the owner disallowed, or too often | robots.txt checked first, a named user agent, a cache, 10 s timeout, 2 MB limit, only http(s) | `test_fetcher_caches_respects_robots_and_handles_errors` |
| Spend | A visitor or a loop runs up model and search costs | Cost cap per run ($0.25), 2 searches per question, 3 briefs per visit, 30 briefs and $3 per day; Anthropic Console monthly limit | `test_the_whole_pipeline_and_its_cost_cap`, `test_limits` |
| Secrets | API key leaked | Only in `.env` or host secrets; never printed; gitleaks in CI and pre-commit | gitleaks job |

## OWASP Top 10 for LLM applications (2025)

| # | Risk | How it's handled |
|---|---|---|
| LLM01 | Prompt injection | Web content is labelled data; the critic and the writing check are code; the writer sees only findings |
| LLM02 | Sensitive information disclosure | Themes, not individuals; redaction; the eval's personal-data check |
| LLM03 | Supply chain | Pinned dependencies, pip-audit, Dependabot, gitleaks |
| LLM04 | Data and model poisoning | Every claim keeps its URL and quote, and the quote is re-checked on the page |
| LLM05 | Improper output handling | The brief is Markdown text shown, never executed; links are the cited URLs |
| LLM06 | Excessive agency | Read-only: it searches and reads pages; it never sends the outreach email (it's a draft) |
| LLM07 | System prompt leakage | No secrets in prompts |
| LLM08 | Vector and embedding weaknesses | No embeddings; the chat's BM25 runs over the brief's own findings |
| LLM09 | Misinformation | Sources per line, quote-on-page status, stale news flagged, fictional companies in the eval |
| LLM10 | Unbounded consumption | Per-run cost cap, per-question search limit, per-visit and per-day caps |
