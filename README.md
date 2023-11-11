# Bunq utilities <!-- omit from toc -->

- [Getting started](#getting-started)
  - [Create bunq config](#create-bunq-config)
  - [Start server](#start-server)
- [Development](#development)
  - [Rules model](#rules-model)

## Getting started

### Create bunq config

Using Docker:

`docker run --rm -v bunq_data:/app/conf besquared/bunq python app.py --production --config-file conf/.bunq.conf create-config --api-key <API-KEY>`

Using python
`python ./app.py --production --config-file conf/.bunq.conf create-config --api-key <API-KEY>`

### Start server

Using Docker compose:
`docker compose up -d`

## Development

### Rules model

To generate the model from the schema, run the following command:

`datamodel-codegen --input-file-type jsonschema --input schema/rules.schema.json --output-model-type pydantic_v2.BaseModel --output schema/rules_model.py --class-name RuleCollection --use-title-as-name --disable-appending-item-suffix`