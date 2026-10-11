.PHONY: eval baseline test audit gold api docker-up terraform-fmt terraform-validate

eval baseline:
	python3 eval/run_eval.py --static

gold:
	python3 src/evaluation_data/build_gold_v1.py

audit:
	python3 eval/run_eval.py --static | head -40

test:
	python3 -m pytest tests/test_p0_phase0.py -v

api:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000

docker-up:
	docker compose up --build

terraform-fmt:
	terraform -chdir=infra/terraform fmt

terraform-validate:
	terraform -chdir=infra/terraform init -backend=false
	terraform -chdir=infra/terraform validate
