# Bunq utilities <!-- omit from toc -->

- [Getting started](#getting-started)
  - [Create bunq config](#create-bunq-config)
- [Development](#development)
  - [Rules model](#rules-model)

## Getting started

### Create bunq config

`./app.py --production --config-file .bunq.conf create-config --api-key <API-KEY>`

## Development

### Rules model

To generate the model from the schema, run the following command:

`datamodel-codegen --input-file-type jsonschema --input schema/rules.schema.json --output-model-type pydantic_v2.BaseModel --output schema/rules_model.py --class-name RuleCollection --use-title-as-name --disable-appending-item-suffix`