.PHONY: setup fmt lint pylint check hooks-run

setup:
	python3.12 -m venv .venv
	. .venv/bin/activate && pip install -U pip
	. .venv/bin/activate && pip install -r requirements-dev.txt
	. .venv/bin/activate && pre-commit install
	cp scripts/pre-push .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	@echo "✅ Ready. Drop your module into / and commit."

fmt:
	. .venv/bin/activate && ruff format

lint:
	. .venv/bin/activate && ruff check

pylint:
	. .venv/bin/activate && pylint

check:
	$(MAKE) fmt
	$(MAKE) lint
	$(MAKE) pylint

hooks-run:
	. .venv/bin/activate && pre-commit run --all-files
