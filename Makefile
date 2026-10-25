.PHONY: check lint test gates app

check: lint test gates

lint:
	ruff check .
	ruff format --check .

test:
	python -m pytest --cov --cov-fail-under=80

gates:
	python -m eval.run_eval --rescore eval/reports/research-2026-10-25-dev.jsonl

app:
	streamlit run app.py
