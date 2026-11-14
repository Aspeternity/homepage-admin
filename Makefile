.PHONY: test run build package

VERSION ?= 0.5.6

test:
	python -m pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload

build:
	docker build -t homepage-admin:$(VERSION) .

package:
	mkdir -p dist
	git archive --format=zip --prefix=homepage-admin-v$(VERSION)/ --output=dist/homepage-admin-v$(VERSION).zip HEAD
	git archive --format=tar.gz --prefix=homepage-admin-v$(VERSION)/ --output=dist/homepage-admin-v$(VERSION).tar.gz HEAD
	git archive --format=zip --output=dist/homepage-admin-v$(VERSION)-web-upload.zip HEAD
	cd dist && sha256sum homepage-admin-v$(VERSION).zip homepage-admin-v$(VERSION).tar.gz homepage-admin-v$(VERSION)-web-upload.zip > SHA256SUMS
