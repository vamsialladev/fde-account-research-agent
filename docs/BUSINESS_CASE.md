# Business case

> Projection from stated assumptions, not a measurement. The only measured input is the AI cost per brief (from
> the saved eval reports). The hotel engagement this belongs to is simulated, and there are no real users.

## The problem in business terms

Before a first meeting with a new account, an engineer spends a couple of hours reading the company's website,
filings, news and guest reviews, then writes notes and questions. That's time not spent on delivery, and the
result varies by person: some arrive with ten sharp questions, some with none. When the prep is rushed, the first
meeting is spent on basics the client expects you to know already.

## Who benefits

- **Engineers running discovery** (FDEs, solutions engineers): less time gathering, more time thinking about the
  questions.
- **Their lead:** a consistent brief for every first meeting, with sources anyone can check.
- **The client:** a first meeting that starts from what's public and gets to their real problems sooner.

## Assumptions, and why

| Assumption | Base | Why |
|---|---|---|
| First meetings per engineer per month | 4 | New accounts plus new stakeholders at existing ones; a guess for a busy field team |
| Manual prep per meeting | 2.5 h | Reading a website, an annual report, recent news and a review site, then writing notes |
| Share of prep the brief replaces | 40% | It replaces gathering and summarizing, not deciding what matters |
| Review time added per brief | 15 min | Checking the sources before quoting anything (the brief says to) |
| Loaded cost per hour | $95 | A senior engineer's salary plus overhead |
| Briefs per meeting | 1.5 | Some accounts get a second brief after the first call |
| AI cost per brief | $0.14 | **Measured** in the research eval (2026-10-25); `--cost-per-brief` to change it |
| Hosting | $25 / month | A small always-on app; Streamlit Community Cloud is free |

## Projected results (team of 8, per year)

Run `python scripts/business_case.py --scenarios`:

| Line | Pessimistic | Base | Optimistic |
|---|---|---|---|
| First meetings | 192 | 384 | 576 |
| Hours saved | 16 | 288 | 696 |
| Time saved | $1,520 | $27,360 | $66,120 |
| AI cost | $40 | $81 | $121 |
| Hosting | $300 | $300 | $300 |
| **Net value** | **$1,180** | **$26,979** | **$65,699** |

## Sensitivity

- **Review time is the swing factor.** If checking a brief takes as long as the prep it replaced, the saving is
  zero (a test covers it). That's why every line cites a numbered source and the brief says whether the quote was
  found on the page: checking should take minutes, not an hour.
- **AI cost doesn't matter at this scale.** Doubling it to $0.28 a brief moves the base case by $81 a year.
- **Pessimistic** halves the meetings, halves the share replaced and adds 10 minutes of review: still positive,
  barely.

## Value not in the numbers

- Fewer meetings spent on basics; better first impressions.
- A brief that's the same shape every time, so a lead can review prep in two minutes.
- Fictional or obscure companies get "no reliable public information was found" instead of a confident invented
  profile. That's a risk avoided, not a saving.

## Pilot plan (4 weeks)

1. Week 1: two engineers prepare their next first meetings the old way and time it (the baseline).
2. Weeks 2–3: the same engineers use the brief for their next meetings, and time prep including review.
3. After each meeting, the engineer marks each brief line: used / not used / wrong.
4. Week 4: compare, and read every line marked wrong.

## KPIs with go / no-go

| KPI | Go | No-go |
|---|---|---|
| Prep time per meeting, including review | At least 30% lower than the baseline | Less than 10% lower |
| Brief lines marked wrong | Under 2% | Any wrong fact quoted to a client |
| Lines used in the meeting or the notes | At least a third | Under 10% |
| Cost per brief | Under $0.50 | Over $1.00 |
| Engineers who'd keep using it | Both | Neither |

## Risks

| Risk | Mitigation |
|---|---|
| A wrong fact gets quoted to a client | Every line cites a source; quotes are re-checked on the page; the brief says "check before quoting" |
| Personal data about private people (reviewers) | Themes only; redaction; an eval check fails any email address or phone number |
| Sites that don't want to be read | robots.txt checked before any fetch; disallowed pages are skipped and counted |
| Search costs run away | A hard cost cap per run, plus per-visit and per-day caps |
| Engineers stop thinking and read the brief out | The questions are a starting point; the pilot measures what was actually used |
