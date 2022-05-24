lint:
	pipenv run mypy .
	pipenv run isort --profile black .
	pipenv run black .
