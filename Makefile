default: build

build:
	docker build -f Dockerfile -t rdbox_app_market . --no-cache

local-bot: build
	docker run -it --rm -v ~/.ssh/id_rsa:/root/.ssh/id_rsa rdbox_app_market python3 -m rdbox_app_market bot-gen

local-manually: build
	docker run -it --rm -v ~/.ssh/id_rsa:/root/.ssh/id_rsa rdbox_app_market python3 -m rdbox_app_market manually

release-bot: build
	docker run -i --rm -v ~/.ssh/id_rsa:/root/.ssh/id_rsa -v /tmp:/tmp rdbox_app_market python3 -m rdbox_app_market bot-gen --publish

release-manually: build
	docker run -i --rm -v ~/.ssh/id_rsa:/root/.ssh/id_rsa -v /tmp:/tmp rdbox_app_market python3 -m rdbox_app_market manually --publish