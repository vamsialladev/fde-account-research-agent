# Decisions

Each one: context, decision, tradeoff, result.

## 1. Four small agents instead of one long one

- **Context:** a brief someone takes into a client meeting has to be right more than it has to be long. One agent
  that searches, writes and checks itself has no independent check.
- **Decision:** planner → researchers (one per topic) → critic → writer. The critic is code, not a model: it can't be
  talked into keeping a claim. The writer only sees the findings the critic kept, and its lines are dropped if they
  cite nothing.
- **Tradeoff:** more calls than one agent (8 model calls and about 12 searches a brief), and the writer can't add
  context it "just knows".
- **Result:** every line in a brief cites a numbered source; the eval counts how many research sentences had no
  source and were removed.

## 2. Anthropic's web search tool, the basic version, over Tavily

- **Context:** the plan allowed the Anthropic web search tool or Tavily.
- **Decision:** Anthropic's `web_search_20250305` with `max_uses` per question. One provider, one key, and the
  answer comes back with citations (URL, title, the cited text) attached to each piece of text, which is exactly
  what the critic needs. The dynamic-filtering version (`web_search_20260209`) was tried first and errored on
  Claude Haiku 5.5 in a probe, so the basic one is the default (`WEB_SEARCH_TOOL` to change it).
- **Tradeoff:** $10 per 1,000 searches is most of a brief's cost (about 12 searches, 12 cents); no control over
  which search engine is used.
- **Result:** see the cost per brief in [Results](../README.md#results).

## 3. The critic re-reads each cited page, politely

- **Context:** a citation can point to a page that doesn't say what the sentence claims.
- **Decision:** for every source, fetch the page with a clear user agent, check robots.txt first, cache it, and look
  for the cited text on it (or 12 consecutive words of it). Pages robots.txt disallows are not fetched and are
  marked "robots.txt", neither verified nor removed.
- **Tradeoff:** about 30 seconds a brief; some sites block automated readers entirely (marked "unreachable").
- **Result:** the brief lists, per source, whether its quote was found on the page.

## 4. A hard cost cap per run

- **Context:** a public demo with web search could get expensive if a run loops or a company is huge.
- **Decision:** `RUN_COST_CAP_USD` (default $0.25): no new research starts once the run is within $0.02 of the cap,
  so the writer can still finish. Each question has at most 2 searches; the critic sends work back once, for at most
  two thin topics, only if there's budget. Per visit 3 briefs; per day 30 briefs and $3 across visitors.
- **Tradeoff:** a capped brief is thinner, and says so.
- **Result:** the eval reports how many runs hit the cap.

## 5. No personal data about private individuals

- **Context:** guest reviews are written by private people; meeting prep doesn't need their names.
- **Decision:** the researcher prompt asks for themes across reviews, never individuals; the critic scrubs emails,
  phone numbers and names after phrases like "my name is" (stage 1's redaction) and flags the finding; the eval
  fails a brief with any email address or phone number. Executives named in public company filings are public
  figures and are allowed.
- **Tradeoff:** pattern-based, so an unusual name in a review quote could slip through; the brief only ever states
  themes, which keeps quotes out.
- **Result:** the `no_personal_data` check in the eval.

## 6. Fictional companies are part of the eval on purpose

- **Context:** the easiest way for a research agent to look good is to invent plausible facts.
- **Decision:** three fictional hotel groups (two dev, one held-out) with no web presence. Passing means no fact
  lines and the brief saying no reliable public information was found.
- **Tradeoff:** a real company with a similar name could be found instead; the researcher is told to say so.
- **Result:** the `fictional_honest` check in the eval.

## 7. A chat about the brief, with no new searches

- **Context:** the checklist asks for a real chat; a chat that searches again would cost as much as a new brief.
- **Decision:** questions are answered only from the brief's own findings (BM25 over them), citing finding ids;
  follow-ups are rewritten first. Conversations live in the browser tab; a brief and its chat can be shared as a
  read-only link (the content is inside the link).
- **Tradeoff:** the chat can't learn anything new; it says so and suggests what to ask in the meeting instead.
- **Result:** a chat turn costs about a tenth of a cent.

## 8. The outreach email doesn't describe the sender (pilot run, 2026-10-25)

- **Context:** the first eval run was stopped after 5 briefs because reading them showed two problems the checks
  didn't. The email for one company opened "I'm a Forward Deployed Engineer", and two others said "I'm Vamsi, an
  engineer working on…". The brief is signed "Vamsi", whose title is Senior Software Engineer, so the email
  claimed a title Vamsi doesn't hold. Also, the fictional company's brief had no use-case hypotheses: the writer
  prompt said both "exactly 3" and "a line with no finding to cite must not be written".
- **Decision:** the writer prompt now says not to describe the sender at all (no title, role or employer), and to
  write 3 common use cases with no findings and every check "unknown" when nothing supports any. A new
  deterministic check, `email_no_title`, fails an email that says "I'm (Vamsi,) a/an … engineer / developer /
  consultant / founder / architect". It's unit-tested on the phrasings the pilot produced.
- **Tradeoff:** the email is less personal. Use cases with no findings could be mistaken for research; the table
  shows no source next to them and every check says "unknown".
- **Result:** the pilot is kept as measured (`research-2026-10-25-dev-pilot.jsonl`): 4/5 briefs passed the checks
  that existed then, and 2/5 pass once it's re-scored with the new check. See the final runs in the README.

## 9. Two checks fixed after reading the final run; one real miss kept

- **Context:** reading every failing brief in the final dev run (not just the scores) showed three kinds of
  failure. Hyatt run 1 failed `no_hype` because a cited page's title in the Sources list was "…a more personalized
  and seamless travel experience": a source's title, not the agent's words. Seabright run 1 failed
  `fictional_honest` because the brief said "No reliable public information was found" and then named, with
  sources, the different businesses with similar names, which is what decision 6 asks for; the check required
  zero research lines. Alpine Pines Lodge Group run 2 presented "Alpine Lodge in North Creek, New York" as its only
  finding without saying it's a different business. That one is a real miss.
- **Decision:** `no_hype` reads only the brief's body (everything before Sources). `fictional_honest` now allows
  research lines for a fictional company only if each one says nothing reliable was found or that a match is a
  different entity ("different entity / company / business", "does not match", "unrelated"). Both are unit-tested
  with the real phrasings, including a made-up fact that must still fail. The saved runs were re-scored without
  calling the model (`--rescore --write`), and the as-measured reports are kept next to them.
- **Tradeoff:** a phrase list can be gamed by a brief that says "different business" and then states invented
  facts in the same line. The labelled sample (the validation checklist) is the check on that.
- **Held-out:** run 2 of the fictional Harbor & Hearth Hotels said "a different kind of business" and "similarly
  named but separate businesses", which the first pattern missed. I widened it to those phrasings (tested) before
  re-scoring, and kept the as-measured held-out report. Run 1 of the same company stated a pizza pop-up and a
  listing's locations as if they were the company; that still fails and is a real held-out miss.
- **Result:** dev 15/18 as measured → 17/18; held-out 3/6 → 4/6. Still failing, and reported rather than tuned
  for: Alpine Pines run 2 and Harbor & Hearth run 1 (a near match stated as the company), and Harbor & Hearth run 3,
  which is borderline: it marks most near matches as other businesses but still presents an undated acquisition by
  "a differently spelled name" as possibly the same company. I didn't widen the pattern again to pass it: a third
  change fitted to held-out output would stop being a check. Numbers: [Results](../README.md#results).

## 10. Example briefs for everyone, live runs behind a code or a small daily cap (2026-10-25)
- **Context:** every live brief costs 10-15 cents in model calls and paid web search, and the app is public.
- **Decision:** three real briefs from the saved 2026-10-25 eval run (run 1 of Hyatt, Club Med, Four Seasons, each of
  which passed every check) are copied unchanged into `data/examples/` and open for free, labelled with their date.
  A live run needs `DEMO_CODE`, or counts against 3 a day across everyone. `MONTHLY_COST_CAP_USD` stops live runs for
  the month, read from the durable ops log (Neon) so a restart can't reset it.
- **Trade-off:** example briefs go stale as companies change; the label says when they were made.
- **Result:** a visitor sees the product working with no spend; the worst case is the monthly cap.

## 11. Shared guardrails, tracing from the pipeline's own steps, planted instructions removed by the critic (2026-10-25)
- **Context:** the final plan adds guardrails, a red team, tracing, one ops log and an Admin page to every live app.
- **Decision:** wire hotel-ai-platform v0.1.3 (`src/research/ops.py`); `pipeline._record` also records each step as a
  span with its cost; the critic removes planted instructions from findings and drops a finding that's only an
  instruction. Promise and citation wording checks are off: the agent only reads, and cites findings by ID.
- **Trade-off:** none of the 538 saved findings matched the planted-instruction patterns, so the check is untested on
  real pages; it's tested on the red-team cases.
- **Result:** red team shared 48/48 (four documented overrides); own 11 held-out cases 10/11 on the first run.
