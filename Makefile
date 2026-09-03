.PHONY: install update test art

install:
	pip install -e ".[dev]"

update:
	GITHUB_TOKEN=$$(gh auth token) python -m profilecard

test:
	pytest

# one-off: regenerate art.json from a portrait (needs `pip install -e ".[art]"`)
art:
	python tools/make_art.py $(PHOTO) --cols 80
