.PHONY: dev build stop clean test-transcription logs shell

# Load .env file if it exists
ifneq ("$(wildcard .env)","")
    include .env
    export $(shell sed 's/=.*//' .env)
endif

dev: build
	docker-compose up -d

build:
	docker-compose build

stop:
	docker-compose stop

clean:
	docker-compose down -v
	rm -rf data/test_bench/*

# Standalone benchmarking tool (runs outside docker or inside via exec)
test-transcription:
	python3 -m src.test_transcriptions $(FILE) --providers $(PROVIDERS)

shell:
	docker-compose exec discovery-worker sh

logs:
	docker-compose logs -f

