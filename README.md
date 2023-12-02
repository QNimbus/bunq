# Bunq utilities <!-- omit from toc -->

- [Getting started](#getting-started)
  - [Create bunq config](#create-bunq-config)
  - [Start server](#start-server)
- [Development](#development)
  - [Rules model](#rules-model)

## Getting started

### Create bunq config

Using Docker:

`docker run --rm -v conf:/app/conf besquared/bunq:latest python app.py --production --config-file conf/.bunq-<CONFIG-NAME>.conf create-config --api-key <API-KEY>`

or (get the file in the current workdir):

`docker run --rm -v ${PWD}:/app/conf besquared/bunq:latest python app.py --production --config-file conf/.bunq-<CONFIG-NAME>.conf create-config --api-key <API-KEY>`

Using python (inside container)
`python app.py --production --config-file conf/.bunq-<CONFIG-NAME>.conf create-config --api-key <API-KEY>`

Using docker compose (when stack _is not_ running)
`docker compose -f docker-compose.yaml run --no-deps --rm bunq python app.py --production --config-file conf/.bunq-<CONFIG-NAME>.conf create-config --api-key <API-KEY>`

Using docker compose (when stack _is_ running)
`docker compose -f docker-compose.yaml exec bunq python app.py --production --config-file conf/.bunq-<CONFIG-NAME>.conf create-config --api-key <API-KEY>`

### Start server

Using Docker compose:
`docker compose up -d`

### Flush Redis database

Using Docker compose:
`docker compose -f docker-compose.yaml exec -it -e PYTHONPATH=/app bunq python /app/libs/redis_wrapper.py flushdb`

Or inside the container:
`libs/redis_wrapper.py flushdb`

## Development

### Rules model

To generate the rules collection model from the schema, run the following command:

`datamodel-codegen --input-file-type jsonschema --input schema/rules.schema.json --output-model-type pydantic_v2.BaseModel --output schema/rules_model.py --class-name RuleCollection --use-title-as-name --disable-appending-item-suffix`

To generate the callback model from the schema, run the following command:

`datamodel-codegen --input-file-type jsonschema --input schema/callback.schema.json --output-model-type pydantic_v2.BaseModel --output schema/callback_model.py --class-name CallbackModel --use-title-as-name --disable-appending-item-suffix`
