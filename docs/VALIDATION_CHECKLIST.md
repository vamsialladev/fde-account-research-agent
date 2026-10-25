# Validation checklist (things only the owner can do)

## 1. Label the claims (the unsupported-claim rate)

The eval's checks are deterministic: they prove every line has a source and the quote is on the page, but not
that the sentence says what the source says. That needs a person.

1. `python -m eval.run_eval --sample eval/reports/research-2026-10-25-dev.jsonl` writes 30 random claims to
   `eval/reports/research-2026-10-25-dev-labels.csv`.
2. For each row, open `source_url`, read around the quote, and fill `supported` with yes, no or partly. Add a note
   for anything not "yes".
3. Report the rate as "unsupported claims: N of 30 labelled", with the date. Don't round it into a percentage of all
   claims; it's a sample.

## 2. Deploy and check the live app

1. Follow "YOUR CLICKS" in `PROGRESS.md` (Streamlit Community Cloud, secret `ANTHROPIC_API_KEY`).
2. Set a monthly spending limit in the Anthropic Console before sharing the link.
3. On the live app, type the three inputs in `docs/VIDEO_SCRIPT.md` and check: the steps appear, every line has a
   source number, input 3 says no reliable public information was found, and the share link opens read-only.

## 3. Record the video

Follow `docs/VIDEO_SCRIPT.md` and the recording guide. Put the MP4 in `docs/video/`, then run
`python scripts/make_captions.py` and replace the `<!-- DEMO-VIDEO -->` line in the README.
