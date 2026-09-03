.PHONY: update

update:
	GITHUB_TOKEN=$$(gh auth token) python3 update_profile.py
