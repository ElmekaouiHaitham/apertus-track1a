.PHONY: run test live report
run:
	docker build -t apertus-choice-audit .
	docker run --rm -v "$(CURDIR)/output:/audit/output" apertus-choice-audit
test:
	python -m unittest discover -s tests
live:
	docker build -t apertus-choice-audit .
	docker run --rm -e LLM_NAME -e LLM_BASE_URL -e LLM_API_KEY -v "$(CURDIR)/output:/audit/output" apertus-choice-audit python src/live_replay.py --finding all
report:
	tectonic --outdir . docs/report.tex
	python -c "from pathlib import Path; Path('report.pdf').replace('ApertusChoiceAudit_Report.pdf')"
