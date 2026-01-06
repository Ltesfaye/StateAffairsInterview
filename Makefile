.PHONY: dev build stop clean test-transcription logs shell

# Load .env file if it exists
ifneq ("$(wildcard .env)","")
    include .env
    export $(shell sed 's/=.*//' .env)
endif

dev: launch

build:
	docker-compose build
	$(MAKE) launch

launch:
	docker-compose up -d
	@echo "Waiting for dashboard to start..."
	@(sleep 5 && open http://localhost:8501 || echo "Could not open browser automatically. Visit http://localhost:8501") &
	docker-compose logs -f

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

