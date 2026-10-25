# Video script: Account Research Agent (about 80 seconds)

How I talk in this one: like I'm showing it to a colleague before a client call. Short sentences, contractions, a
pause where there's a `/`. Talk from the bullets, not word for word. One take with a small stumble is fine.

Before recording: the live app, awake (open it a minute before), browser zoom 110%, a fresh tab (no briefs yet).
A brief takes about 90 seconds, so start input 1, keep talking over the steps, and cut the wait in editing. No
secrets on screen.

## Shot list

| Time | On screen | What I say |
|---|---|---|
| 0–10 s | The empty form | Before a first client meeting, I spend a couple of hours reading about the company. / This does the gathering for me, / and every line it writes has a source. |
| 10–25 s | Type input 1, press Research. The status shows planner, researchers, critic, writer | I'll try Club Med. / A planner writes six questions, / researchers search the web for each one, / then a critic checks the work. The critic is plain code, not a model. |
| 25–45 s | The finished brief: Snapshot with numbered sources, then scroll to Sources with "quote on page: found" | Every line cites a numbered source. / And for each source, it went back to the page / and checked the quoted text is really there. / Lines with no source were removed before I ever saw them. |
| 45–55 s | Scroll: ten questions, three use cases with the 4-check, the email | Then ten questions for the meeting, / three use-case guesses with what we don't know yet, / and a short email asking for a call. |
| 55–65 s | "Ask about it" tab: type input 2; the answer cites finding ids | I can ask about the brief. / It answers only from what it found. No new searches. |
| 65–75 s | New tab: type input 3. The brief says "no reliable public information was found" | And this company doesn't exist. / The easy failure is to make something up. / It says it found nothing reliable. That's in the eval, three runs, every time. |
| 75–80 s | The live URL in the address bar | It's live, link below. Simulated engagement, public web pages only. |

## Exact inputs

| # | Where | Type exactly |
|---|---|---|
| 1 | Form | Company `Club Med`, website `clubmed.com` |
| 2 | "Ask about it" tab | `What do guests complain about most?` |
| 3 | Form (new tab) | Company `Seabright Coastal Resorts`, website empty |

Checked 2026-10-25 with the live model. In a local run of the app: input 1 gave 42 sourced findings, 22 of 30
quotes found on their pages, $0.14, 83 s; input 2 answered from one finding (F22) and said the findings don't show
which complaint is most common; the share link opened the read-only brief. Through the same pipeline: input 3 passed
every eval check with the "no reliable public information" line. Type all three on the live app once it's
deployed, before recording. Club Med's findings change with the news.

## LinkedIn caption (one sentence)

I built an account research agent that writes a cited brief for a first client meeting, checks every quote on
its page, and says "nothing reliable found" instead of inventing a company.
