.PHONY: test run build release

VERSION ?= 0.2.0

run:
	uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload

test:
	pytest -q

build:
	docker build -t homepage-admin:$(VERSION) .

release:
	cd .. && rm -f homepage-admin-v$(VERSION).zip homepage-admin-v$(VERSION).tar.gz
	cd .. && zip -r homepage-admin-v$(VERSION).zip homepage-admin-v0.2.0 -x '*/__pycache__/*' '*.pyc' '.git/*' '.pytest_cache/*'
	cd .. && tar --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' -czf homepage-admin-v$(VERSION).tar.gz homepage-admin-v0.2.0
