.PHONY: build up down logs test package

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f homepage-admin

test:
	python -m pytest -q

package:
	cd .. && zip -r homepage-admin-v0.1.1.zip homepage-admin-v0.1.1-release -x '*/__pycache__/*' '*.pyc' '.git/*'
