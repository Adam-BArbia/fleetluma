"""FL-6: Validate design-time OpenAPI schema and JSON examples.

This is contract validation, not a running FastAPI integration test.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver
from openapi_spec_validator import validate_spec

BASE = Path(__file__).resolve().parent
document = json.loads((BASE / "openapi.json").read_text(encoding="utf-8"))
validate_spec(document)

schemas = document["components"]["schemas"]
cases = {
    "agent-report.json": "AgentReport",
    "accepted.json": "Accepted",
    "hosts.json": "HostList",
    "host-history.json": "HostHistory",
    "processes.json": "ProcessSnapshot",
    "services.json": "ServiceList",
    "service-checks.json": "ServiceChecks",
    "error.json": "ApiError",
}

for file_name, schema_name in cases.items():
    example = json.loads((BASE / "examples" / file_name).read_text(encoding="utf-8"))
    # Resolve local OpenAPI component references with the full contract document.
    validator = Draft202012Validator(
        {"$ref": f"#/components/schemas/{schema_name}",
         "components": document["components"]},
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    validator.validate(example)
    print(f"PASS {file_name} as {schema_name}")

assert len(document["paths"]) == 7
assert len(cases) == 8
print("PASS OpenAPI specification and all eight sample bodies")
