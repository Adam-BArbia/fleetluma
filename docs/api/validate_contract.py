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
    "pairing-created.json": "PairingCreated",
    "pairing-resolved.json": "PairingResolved",
    "pairing-approval.json": "PairingApprovalResult",
    "workspaces.json": "WorkspaceList",
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

# Preserve the seven existing monitoring resources while adding pairing,
# workspace discovery, device management and revocation contracts.
expected_operations = {
    ("post", "/api/v1/agent/reports"),
    ("get", "/api/v1/hosts"),
    ("get", "/api/v1/hosts/{id}"),
    ("get", "/api/v1/hosts/{id}/history"),
    ("get", "/api/v1/hosts/{id}/processes"),
    ("get", "/api/v1/services"),
    ("get", "/api/v1/services/{id}/checks"),
    ("post", "/api/v1/agent/pairings"),
    ("post", "/api/v1/agent/pairings/token"),
    ("post", "/api/v1/agent/pairings/cancel"),
    ("post", "/api/v1/operator/pairings/resolve"),
    ("post", "/api/v1/operator/pairings/{id}/approve"),
    ("post", "/api/v1/operator/pairings/{id}/deny"),
    ("get", "/api/v1/operator/workspaces"),
    ("get", "/api/v1/operator/hosts"),
    ("patch", "/api/v1/operator/hosts/{id}"),
    ("post", "/api/v1/operator/hosts/{id}/revoke"),
    ("get", "/api/v1/operator/device-audit"),
}
actual_operations = {
    (verb, path)
    for path, path_item in document["paths"].items()
    for verb in path_item if verb in {"get", "post", "patch", "put", "delete"}
}
assert actual_operations == expected_operations, (
    f"Missing: {expected_operations - actual_operations}; "
    f"extra: {actual_operations - expected_operations}"
)
assert len(cases) == 12
for method, path in expected_operations:
    operation = document["paths"][path][method]
    assert operation.get("responses")
    if path.startswith("/api/v1/operator/") or (
        method == "get" and
        (path.startswith("/api/v1/hosts") or path.startswith("/api/v1/services"))
    ):
        assert operation.get("security") == [{"OperatorJwt": []}], (method, path)
print(f"PASS OpenAPI specification, {len(expected_operations)} operations and {len(cases)} sample bodies")
