lint:
	pipenv run mypy cli gira
	pipenv run isort --profile black .
	pipenv run black .
