default: build

build:
	docker build -f Dockerfile -t rdbox_app_market .

at-local: build
	docker run -it --rm -v ~/.ssh/id_rsa:/root/.ssh/id_rsa rdbox_app_market python3 -m rdbox_app_market

