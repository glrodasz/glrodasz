.PHONY: update

update:
	GITHUB_TOKEN=$$(gh auth token) python3 update_profile.py

.PHONY: art

# one-off: regenerate art.json from a portrait (needs pillow+numpy)
art:
	python3 make_art.py $(PHOTO) --cols 80
