.PHONY: test run build package

VERSION ?= 0.3.0
PROJECT_DIR := homepage-admin-v0.3.0

test:
	python -m pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload

build:
	docker build -t homepage-admin:$(VERSION) .

package:
	cd .. && zip -r homepage-admin-v$(VERSION).zip $(PROJECT_DIR) -x '*/__pycache__/*' '*.pyc' '.git/*' '.pytest_cache/*'
	cd .. && tar --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' -czf homepage-admin-v$(VERSION).tar.gz $(PROJECT_DIR)
