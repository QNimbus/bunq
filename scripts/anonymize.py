#!/usr/bin/env -S python -W ignore

# anonymize.py

# Standard library imports
import json
import uuid
import random
import argparse

# Third-party imports
from faker import Faker

# Local application/library imports
# ...


fake = Faker()


def anonymize_data(data, anonymization_rules):
    """Recursively anonymize specific fields in the given data."""
    if isinstance(data, dict):
        return {key: anonymize_value(key, value, anonymization_rules) for key, value in data.items()}

    if isinstance(data, list):
        return [anonymize_data(item, anonymization_rules) for item in data]

    return data


def anonymize_value(key, value, anonymization_rules):
    """Anonymize individual value based on the key using provided faker functions."""
    if key in anonymization_rules:
        faker_function = anonymization_rules[key]
        return faker_function()

    if isinstance(value, (dict, list)):
        return anonymize_data(value, anonymization_rules)

    return value


def anonymize_json_file(input_file, output_file, anonymization_rules):
    """Read JSON from file, anonymize it, and write to another file."""
    with open(input_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    anonymized_data = anonymize_data(data, anonymization_rules)

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(anonymized_data, file, indent=4)


def main():
    """
    Anonymizes the JSON data in the specified file.

    Args:
        file (str): The JSON file to be anonymized.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Anonymize JSON data.")
    parser.add_argument("file", help="The JSON file to be anonymized")

    args = parser.parse_args()

    input_file = args.file
    output_file = f"{input_file}.anon.json"

    anonymization_rules = {
        "created": lambda: fake.date_time_this_month().isoformat(" "),
        "updated": lambda: fake.date_time_this_month().isoformat(" "),
        "name": fake.name,
        "display_name": fake.name,
        "city": fake.city,
        "description": lambda: fake.text(max_nb_chars=80),
        "second_line": lambda: fake.text(max_nb_chars=20),
        "public_nick_name": fake.name,
        "id": lambda: random.randrange(100000, 999999),
        "monetary_account_id": lambda: random.randrange(100000, 999999),
        "iban": fake.iban,
        "url": fake.url,
        "target_url": fake.url,
        "uuid": lambda: str(uuid.uuid4()),
        "anchor_uuid": lambda: str(uuid.uuid4()),
        "attachment_public_uuid": lambda: str(uuid.uuid4()),
        "latitude": lambda: float(fake.latitude()),
        "longitude": lambda: float(fake.longitude()),
        "altitude": lambda: float(random.uniform(0, 1) * 100),
    }

    anonymize_json_file(input_file, output_file, anonymization_rules)
    print(f"Anonymized file saved as: {output_file}")


if __name__ == "__main__":
    main()
