"""Typed tool execution boundary.

Every tool call made by the model runtime, the async runtime, and the HITL
runtime goes through this module. Model-supplied arguments are validated before
the handler runs, and every outcome is normalized to a single ``ToolResult``.

Python callables are validated from their signature with pydantic (lax mode,
so ``"3"`` becomes ``3`` for an ``int`` parameter). Tools whose handler only
accepts ``**kwargs`` and that declare a JSON Schema object (MCP and other
external tools) are validated with ``jsonschema``; that path does not coerce.
Schemas from external servers are untrusted: a ``$ref`` is resolved only
within the schema itself, never fetched from a URL or file.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import inspect
import json
import logging
import weakref
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for
from pydantic import TypeAdapter, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from .models import ToolResult

logger = logging.getLogger(__name__)

ERROR_PREFIX = "Error:"
LEGACY_ERROR_PREFIXES = (
    ERROR_PREFIX,
    "Unknown function:",
    "Rejected by human reviewer:",
)
MAX_ERROR_DETAIL_CHARS = 200
SCHEMA_CACHE_SIZE = 256

# (field path, expected type or None for an unexpected field, problem)
ArgumentError = Tuple[str, Optional[str], str]


def tool_result(
    value: Any,
    *,
    tool_call_id: str = "",
    name: str = "",
) -> ToolResult:
    """Normalize any tool outcome into a ``ToolResult``.

    This is the single point where untyped outcomes become typed results. A
    returned ``ToolResult`` keeps its content, ``is_error`` flag and metadata.
    Strings beginning with a legacy error prefix (``Error:``, ``Unknown
    function:``, ``Rejected by human reviewer:``) are errors, which keeps
    handlers that report failure as text working as before. Any other value
    is converted with ``str()``.
    """
    if isinstance(value, ToolResult):
        return value.model_copy(update={"tool_call_id": tool_call_id, "name": name})
    content = value if isinstance(value, str) else str(value)
    return ToolResult(
        tool_call_id=tool_call_id,
        name=name,
        content=content,
        is_error=content.startswith(LEGACY_ERROR_PREFIXES),
    )


def error_result(content: str, *, tool_call_id: str = "", name: str = "") -> ToolResult:
    """Return an error ``ToolResult`` with the given content."""
    return ToolResult(
        tool_call_id=tool_call_id,
        name=name,
        content=content,
        is_error=True,
    )


def exception_result(exc: BaseException, *, name: str = "") -> ToolResult:
    """Return the error ``ToolResult`` for an exception raised by a handler."""
    return error_result(f"{ERROR_PREFIX} {type(exc).__name__}: {exc}", name=name)


def tool_name(tool_def: Dict[str, Any]) -> str:
    """Return the public name of a legacy tool dict."""
    func = tool_def.get("function")
    return str(tool_def.get("name") or getattr(func, "__name__", "") or "")


def validate_tool_arguments(
    tool_def: Dict[str, Any],
    args: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[ToolResult]]:
    """Validate model-supplied arguments for a legacy tool dict.

    Returns ``(arguments, None)`` with the (possibly coerced) arguments to pass
    to the handler, or ``(args, error)`` where ``error`` is an error
    ``ToolResult`` naming each failing field and its expected type. A tool
    whose arguments cannot be checked is passed through unchanged.
    """
    func = tool_def.get("function")
    if not callable(func):
        return args, None
    signature_validator = _signature_validator(func)
    if signature_validator is not None:
        coerced, errors = signature_validator.validate(args)
    else:
        schema = tool_def.get("parameters")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            return args, None
        schema_validator = cached_schema_validator(schema)
        if schema_validator is None:
            return args, None
        try:
            errors = _json_schema_argument_errors(schema_validator, args)
        except Unresolvable as exc:
            logger.warning(
                "JSON Schema for tool '%s' has an unresolvable $ref; "
                "skipping validation: %s",
                tool_name(tool_def),
                _truncate(str(exc)),
            )
            return args, None
        except RecursionError:
            return args, error_result(
                f"{ERROR_PREFIX} Invalid arguments for tool '{tool_name(tool_def)}': "
                "arguments are nested too deeply to validate",
                name=tool_name(tool_def),
            )
        coerced = args
    if errors:
        return args, error_result(
            _format_argument_errors(tool_name(tool_def), errors),
            name=tool_name(tool_def),
        )
    return coerced, None


def run_tool(tool_def: Dict[str, Any], args: Dict[str, Any]) -> ToolResult:
    """Validate arguments and run a tool synchronously.

    Coroutine handlers are driven to completion on a private event loop.
    Async-only checks are the caller's responsibility, because the direct and
    HITL paths report them differently.
    """
    name = tool_name(tool_def)
    tool_func = tool_def.get("function")
    if not callable(tool_func):
        return error_result(f"{ERROR_PREFIX} Tool function is not callable", name=name)
    arguments, invalid = validate_tool_arguments(tool_def, args)
    if invalid is not None:
        return invalid
    try:
        result = tool_func(**arguments)
        if inspect.iscoroutine(result):
            result = run_coroutine_sync(result)
    except Exception as exc:
        return exception_result(exc, name=name)
    return tool_result(result, name=name)


async def arun_tool(tool_def: Dict[str, Any], args: Dict[str, Any]) -> ToolResult:
    """Validate arguments and run a tool on the caller's event loop."""
    name = tool_name(tool_def)
    tool_func = tool_def.get("function")
    if not callable(tool_func):
        return error_result(f"{ERROR_PREFIX} Tool function is not callable", name=name)
    arguments, invalid = validate_tool_arguments(tool_def, args)
    if invalid is not None:
        return invalid
    try:
        result = tool_func(**arguments)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        return exception_result(exc, name=name)
    return tool_result(result, name=name)


def run_coroutine_sync(coroutine: Any) -> Any:
    """Run a coroutine from synchronous code, inside or outside a loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coroutine))
        return future.result()


@dataclass(frozen=True)
class _ParameterCheck:
    adapter: Optional[TypeAdapter[Any]]
    required: bool
    expected: str


@dataclass(frozen=True)
class _SignatureValidator:
    parameters: Dict[str, _ParameterCheck]
    accepts_extra: bool

    def validate(
        self, args: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[ArgumentError]]:
        coerced: Dict[str, Any] = {}
        errors: List[ArgumentError] = []
        for key, value in args.items():
            check = self.parameters.get(key)
            if check is None:
                if self.accepts_extra:
                    coerced[key] = value
                else:
                    errors.append((key, None, "unexpected argument"))
                continue
            if check.adapter is None:
                coerced[key] = value
                continue
            try:
                coerced[key] = check.adapter.validate_python(value)
            except ValidationError as exc:
                errors.extend(_pydantic_errors(key, check.expected, exc))
        for key, check in self.parameters.items():
            if check.required and key not in args:
                errors.append((key, check.expected, "missing required argument"))
        return coerced, errors


_ValidatorCache = weakref.WeakKeyDictionary[Any, Optional[_SignatureValidator]]
_FUNCTION_VALIDATORS: _ValidatorCache = weakref.WeakKeyDictionary()
_METHOD_VALIDATORS: _ValidatorCache = weakref.WeakKeyDictionary()


def _signature_validator(func: Callable[..., Any]) -> Optional[_SignatureValidator]:
    """Return the cached signature validator for ``func``.

    The cache holds weak references, so it never keeps a handler (or the
    agent or client a closure captures) alive. Bound methods are keyed by
    their underlying function, because a new bound object is created on
    every attribute access.
    """
    underlying = getattr(func, "__func__", None)
    cache, key = (
        (_METHOD_VALIDATORS, underlying)
        if inspect.ismethod(func)
        else (_FUNCTION_VALIDATORS, func)
    )
    try:
        return cache[key]
    except KeyError:
        pass
    except TypeError:
        # Objects that cannot be weakly referenced are validated uncached.
        return _build_signature_validator(func)
    validator = _build_signature_validator(func)
    try:
        cache[key] = validator
    except TypeError:
        pass
    return validator


def _build_signature_validator(
    func: Callable[..., Any],
) -> Optional[_SignatureValidator]:
    """Build a validator from a handler signature.

    Returns ``None`` when the signature carries no argument information: it
    cannot be inspected, or it only accepts ``**kwargs``.
    """
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None

    named_kinds = (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    parameters = list(signature.parameters.values())
    accepts_extra = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters
    )
    named = [param for param in parameters if param.kind in named_kinds]
    if accepts_extra and not named:
        return None
    checks: Dict[str, _ParameterCheck] = {}
    for param in named:
        annotation = _resolve_annotation(func, param.annotation)
        checks[param.name] = _ParameterCheck(
            adapter=_type_adapter(func, param.name, annotation),
            required=param.default is inspect.Parameter.empty,
            expected=_annotation_name(annotation),
        )
    return _SignatureValidator(parameters=checks, accepts_extra=accepts_extra)


def _resolve_annotation(func: Callable[..., Any], annotation: Any) -> Any:
    """Resolve a string annotation (PEP 563) in the handler's module globals.

    Each annotation is resolved on its own, so one unresolvable name only
    disables validation for that parameter.
    """
    if not isinstance(annotation, str):
        return annotation
    target = inspect.unwrap(func)
    namespace = getattr(target, "__globals__", None)
    if namespace is None:
        # Callable instances: resolve in the module that defines ``__call__``.
        namespace = getattr(getattr(target, "__call__", None), "__globals__", None)
    if not isinstance(namespace, dict):
        return annotation
    try:
        return eval(annotation, namespace)  # same resolution as eval_str=True
    except Exception:
        return annotation


def _type_adapter(
    func: Callable[..., Any], parameter: str, annotation: Any
) -> Optional[TypeAdapter[Any]]:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return None
    if isinstance(annotation, str):
        # Unresolvable forward reference; the handler receives the raw value.
        return None
    try:
        return TypeAdapter(annotation)
    except Exception as exc:
        logger.debug(
            "Skipping argument validation for %s.%s: %s",
            getattr(func, "__name__", "tool"),
            parameter,
            exc,
        )
        return None


def _annotation_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "any"
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _pydantic_errors(
    key: str, expected: str, exc: ValidationError
) -> List[ArgumentError]:
    errors: List[ArgumentError] = []
    for detail in exc.errors():
        location = ".".join(str(part) for part in detail.get("loc", ()))
        path = f"{key}.{location}" if location else key
        errors.append((path, expected, str(detail.get("msg", "invalid value"))))
    return errors


def cached_schema_validator(schema: Dict[str, Any]) -> Optional[Validator]:
    """Return a cached validator for a JSON Schema, or ``None`` if invalid.

    The schema's own ``$schema`` dialect is honoured; Draft 2020-12 is used
    when none is declared.
    """
    try:
        key = json.dumps(schema, sort_keys=True)
    except (TypeError, ValueError, RecursionError):
        logger.warning("JSON Schema is not serializable; skipping validation")
        return None
    return _schema_validator_for_key(key)


@functools.lru_cache(maxsize=SCHEMA_CACHE_SIZE)
def _schema_validator_for_key(key: str) -> Optional[Validator]:
    schema = json.loads(key)
    validator_class = validator_for(schema, default=Draft202012Validator)
    try:
        validator_class.check_schema(schema)
    except SchemaError as exc:
        logger.warning("Invalid JSON Schema; skipping validation: %s", exc.message)
        return None
    except RecursionError:
        logger.warning("JSON Schema is nested too deeply; skipping validation")
        return None
    # An empty registry: jsonschema would otherwise fetch remote and file
    # ``$ref`` targets, which an untrusted (MCP) schema can point anywhere.
    validator: Validator = validator_class(schema, registry=Registry())
    return validator


def json_schema_errors(validator: Validator, instance: Any) -> List[str]:
    """Return readable messages for every schema violation in ``instance``."""
    messages: List[str] = []
    for error in sorted(validator.iter_errors(instance), key=_error_sort_key):
        location = _json_path(error.absolute_path)
        messages.append(f"{location}: {_truncate(error.message)}")
    return messages


def _json_schema_argument_errors(
    validator: Validator, args: Dict[str, Any]
) -> List[ArgumentError]:
    errors: List[ArgumentError] = []
    for error in sorted(validator.iter_errors(args), key=_error_sort_key):
        prefix = ".".join(str(part) for part in error.absolute_path)
        error_schema: Any = error.schema
        properties: Any = (
            error_schema.get("properties") if isinstance(error_schema, dict) else None
        )
        if not isinstance(properties, dict):
            properties = {}
        instance = error.instance
        required: Any = error.validator_value
        if (
            error.validator == "required"
            and isinstance(instance, dict)
            and isinstance(required, list)
        ):
            for missing in required:
                if missing not in instance:
                    errors.append(
                        (
                            _join_path(prefix, str(missing)),
                            _schema_type(properties.get(missing)),
                            "missing required argument",
                        )
                    )
        elif error.validator == "additionalProperties" and isinstance(instance, dict):
            for extra in instance:
                if extra not in properties:
                    errors.append(
                        (_join_path(prefix, str(extra)), None, "unexpected argument")
                    )
        elif error.validator == "type":
            errors.append(
                (
                    prefix or "(arguments)",
                    _schema_type(error_schema),
                    f"got {_json_type_name(instance)}",
                )
            )
        else:
            errors.append(
                (
                    prefix or "(arguments)",
                    _schema_type(error_schema),
                    _truncate(error.message),
                )
            )
    return errors


def _error_sort_key(error: Any) -> Tuple[str, str]:
    return (
        ".".join(str(part) for part in error.absolute_path),
        str(error.validator),
    )


def _join_path(prefix: str, name: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _json_path(path: Sequence[Any]) -> str:
    location = "$"
    for part in path:
        location += f"[{part}]" if isinstance(part, int) else f".{part}"
    return location


def _schema_type(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "any"
    value = schema.get("type")
    if isinstance(value, list):
        return " or ".join(str(item) for item in value)
    if value is not None:
        return str(value)
    if "enum" in schema:
        return "one of " + ", ".join(json.dumps(item) for item in schema["enum"])
    return "any"


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _truncate(text: str) -> str:
    if len(text) <= MAX_ERROR_DETAIL_CHARS:
        return text
    return text[: MAX_ERROR_DETAIL_CHARS - 3] + "..."


def _format_argument_errors(name: str, errors: List[ArgumentError]) -> str:
    details = "; ".join(
        (
            f"{field}: {problem}"
            if expected is None
            else f"{field}: {problem}, " f"expected {expected}"
        )
        for field, expected, problem in errors
    )
    return f"{ERROR_PREFIX} Invalid arguments for tool '{name}': {details}"
