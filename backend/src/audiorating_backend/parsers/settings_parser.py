import json
from json import JSONDecodeError


def parse_string_or_json_list(value: str | None, env_var_name: str) -> list[str]:
    """Parse an env var as either a plain string or a JSON list of strings."""
    if value is None or value == "":
        raise ValueError(f"{env_var_name} environment variable is not set.")

    try:
        parsed = json.loads(value)
    except JSONDecodeError:
        parsed = value

    if isinstance(parsed, str):
        if parsed == "":
            raise ValueError(f"{env_var_name} environment variable is not set.")
        return [parsed]

    if isinstance(parsed, list):
        if not parsed:
            raise ValueError(f"{env_var_name} environment variable is not set.")
        if not all(isinstance(item, str) and item != "" for item in parsed):
            raise ValueError(
                f"{env_var_name} must be a string or a JSON list of non-empty strings."
            )
        return parsed

    raise ValueError(f"{env_var_name} must be a string or a JSON list of strings.")


def parse_admin_credentials(
    usernames_value: str | None,
    passwords_value: str | None,
) -> list[tuple[str, str]]:
    """Parse and validate admin usernames/passwords from environment values."""
    usernames = parse_string_or_json_list(usernames_value, "AR_API_ADMIN_USERNAME")
    passwords = parse_string_or_json_list(passwords_value, "AR_API_ADMIN_PASSWORD")

    if len(usernames) != len(passwords):
        raise ValueError(
            "AR_API_ADMIN_USERNAME and AR_API_ADMIN_PASSWORD must contain the same number of entries."
        )

    return list(zip(usernames, passwords))
