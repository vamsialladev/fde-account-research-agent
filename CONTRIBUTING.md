# Contributing

1. Branch from `main` and open a pull request; CI must pass. Commits follow
   [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
2. **A new research topic:** add it to `TOPICS` in `src/research/models.py` and a section for it in
   `src/research/brief.py`. The planner writes one question per topic.
3. **Prompt changes** (planner, researcher, writer, chat): run the dev eval (3 runs) before and after and put both
   numbers in the PR. Read the briefs, not only the scores: decision 8 came from reading them. Run the held-out set
   only when you're done changing things.
4. **A new check:** a pure function in `eval/run_eval.py` `grade()`, a unit test with the phrasings it must pass and
   fail, then `python -m eval.run_eval --rescore <report>.jsonl` on the saved runs. The CI gate fails if a saved
   run's verdicts change, so a new check comes with re-scored reports.
5. **A new company in the eval:** a line in `eval/companies.jsonl` (`split` dev or heldout, `fictional` true for
   a company that doesn't exist). Real companies must be public companies or well-known brands; no private people.
6. Run `make check` before pushing.
