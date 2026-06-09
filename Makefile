.PHONY: setup test test-verbose clean lint

# Agent Assembler Makefile
# Requires: uv (https://docs.astral.sh/uv/)

VENV = .venv
PYTHON = $(VENV)/bin/python3

setup:
	@echo "Setting up virtual environment..."
	uv venv --python 3.11 $(VENV)
	uv pip install -r requirements.txt
	@echo "Done. Run 'make test' to verify."

test:
	$(PYTHON) -m pytest tests/ --tb=short -q

test-verbose:
	$(PYTHON) -m pytest tests/ -v --tb=short

clean:
	rm -rf $(VENV)
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
	find . -name "*.pyc" -delete 2>/dev/null

lint:
	$(PYTHON) -m py_compile api_gateway/core.py
	@echo "Lint OK"
