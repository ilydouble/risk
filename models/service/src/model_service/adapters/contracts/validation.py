from copy import deepcopy

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .common import JsonObject
from .errors import AdapterError
from .io import OperationRequest, OperationResult
from .spec import AdapterSpec, Operation


def _validator(schema: JsonObject) -> Draft202012Validator:
    # Contract schemas may reference their own definitions, never network resources.
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key in {"$ref", "$dynamicRef"}
                    and isinstance(item, str)
                    and not item.startswith("#")
                ):
                    raise AdapterError(
                        "ADAPTER_SCHEMA_INVALID", "Only local schema references are allowed"
                    )
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise AdapterError("ADAPTER_SCHEMA_INVALID", error.message) from error
    return Draft202012Validator(schema)


def validate_json(schema: JsonObject, value: JsonObject, *, code: str) -> None:
    try:
        _validator(schema).validate(value)
    except ValidationError as error:
        path = "/" + "/".join(
            str(x).replace("~", "~0").replace("/", "~1") for x in error.absolute_path
        )
        raise AdapterError(code, error.message, path=path) from error


def parameters_for(spec: AdapterSpec, operation: Operation, parameters: JsonObject) -> JsonObject:
    if operation not in spec.operations:
        raise AdapterError("ADAPTER_OPERATION_UNSUPPORTED", f"Unsupported operation: {operation}")
    definition = spec.operations[operation]

    def merge(base, overrides):
        result = deepcopy(base)
        for key, value in overrides.items():
            result[key] = (
                merge(result[key], value)
                if isinstance(value, dict) and isinstance(result.get(key), dict)
                else value
            )
        return result

    resolved = merge(definition.default_parameters, parameters)
    validate_json(definition.parameters_schema, resolved, code="ADAPTER_PARAMETERS_INVALID")
    return resolved


def validate_request(spec: AdapterSpec, request: OperationRequest) -> None:
    parameters_for(spec, request.operation, request.parameters)
    inputs = spec.operations[request.operation].inputs
    if set(request.inputs) - set(inputs):
        raise AdapterError("ADAPTER_INPUT_INVALID", "Unknown input role")
    for role, definition in inputs.items():
        asset = request.inputs.get(role)
        if asset is None:
            if definition.required:
                raise AdapterError("ADAPTER_INPUT_INVALID", f"Missing input: {role}")
            continue
        path = asset.path
        valid_kind = path.is_file() if definition.kind == "file" else path.is_dir()
        if not valid_kind or path.is_symlink():
            raise AdapterError("ADAPTER_INPUT_INVALID", f"Invalid input path: {role}")
        if definition.formats and asset.format not in definition.formats:
            raise AdapterError("ADAPTER_INPUT_INCOMPATIBLE", f"Unsupported input format: {role}")


def validate_result(spec: AdapterSpec, request: OperationRequest, result: OperationResult) -> None:
    definition = spec.operations[request.operation]
    validate_json(definition.result_schema, result.data, code="ADAPTER_RESULT_INVALID")
    if set(result.artifacts) - set(definition.artifacts):
        raise AdapterError("ADAPTER_RESULT_INVALID", "Unknown artifact role")
    for role, expected in definition.artifacts.items():
        artifact = result.artifacts.get(role)
        if artifact is None and expected.required:
            raise AdapterError("ADAPTER_RESULT_INVALID", f"Missing artifact: {role}")
        if artifact is not None and artifact.format != expected.format:
            raise AdapterError("ADAPTER_RESULT_INVALID", f"Wrong artifact format: {role}")
