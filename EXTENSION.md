# Extension Development Guide

This document describes how to extend RIFT with custom domains, optimizers, data sources, event adapters, and webhooks.

## Extension Architecture

RIFT uses a plugin-based architecture where extensions are discovered at runtime from the `extensions/` directory.

```
extensions/
├── my-domain/
│   ├── manifest.json          # Extension metadata
│   ├── extension.py           # Entry point
│   ├── config.schema.json     # Configuration schema
│   └── README.md
├── my-optimizer/
│   ├── manifest.json
│   └── extension.py
└── ...
```

## Extension Types

### 1. Domain Plugins

Add new problem domains (e.g., traffic, logistics, energy).

```python
# extension.py
from rift.developer.plugin_sdk import DomainPlugin
from rift.models import Scenario, Constraint

class MyDomainPlugin(DomainPlugin):
    @property
    def domain_id(self) -> str: return "my-domain"
    @property
    def display_name(self) -> str: return "My Domain"
    @property
    def description(self) -> str: return "Custom domain description"

    def create_scenario(self, config: dict) -> Scenario:
        # Build Scenario with custom state, interventions, transition, objective
        pass

    def get_policy_variables(self) -> list[str]: return ["var1", "var2"]
    def get_default_perturbations(self) -> list[dict]: return [{"param": 1.0}]
    def get_constraints(self) -> list[Constraint]: return [...]
    def get_objective(self) -> Callable[[dict], float]: return lambda s: 0.0
    def get_transition(self) -> Callable[[dict, dict], dict]: return lambda s, p: s
    def get_interventions(self) -> dict[str, tuple]: return {"action": (0, 1)}
    def validate_config(self, config: dict) -> list[str]: return []

    # Optional: domain-specific Guardian rules
    GUARDIAN_RULES = {
        "CUSTOM-001": {"stage": "STATE", "severity": "HIGH", "action": "WITHHOLD",
                       "check": lambda state: state.get("metric") > threshold,
                       "message": "Custom constraint violated"},
    }

    # Optional: domain-specific visualization
    VISUALIZATION_CONFIG = {
        "state_variables": {...},
        "intervention_variables": {...},
    }
```

**Manifest:**
```json
{
  "id": "my-domain",
  "name": "My Domain",
  "version": "1.0.0",
  "description": "Custom domain for RIFT",
  "author": "Your Name",
  "license": "AGPL-3.0-or-later",
  "rift_version": ">=1.0.0",
  "provides": ["domain"],
  "entry_points": {"domain": "my_domain.MyDomainPlugin"}
}
```

### 2. Optimizer Plugins

Add new optimization algorithms.

```python
class MyOptimizerPlugin(OptimizerPlugin):
    @property
    def optimizer_id(self) -> str: return "my-optimizer"
    @property
    def display_name(self) -> str: return "My Optimizer"

    def supports_backend(self, backend: str) -> bool:
        return backend == "statevector-simulator"

    def optimize(self, scenario: Scenario, **kwargs) -> tuple[dict, float]:
        # Return (assignment, energy)
        return ({"var1": 1, "var2": 0}, 0.0)
```

### 3. Data Source Adapters

Connect external data sources (IoT, FHIR, Kafka, etc.).

```python
class MyDataSourceAdapter(DataSourceAdapter):
    @property
    def source_type(self) -> str: return "my-source"
    @property
    def display_name(self) -> str: return "My Data Source"

    def connect(self, config: dict) -> bool: ...
    def disconnect(self) -> None: ...
    def fetch(self, query: dict) -> list[dict]: ...
    def get_schema(self) -> dict: ...
```

### 3. Event Adapters

Connect event streaming systems (Kafka, NATS, MQTT, etc.).

```python
class MyEventAdapter(EventAdapter):
    @property
    def protocol(self) -> str: return "my-protocol"

    def connect(self, config: dict) -> bool: ...
    def disconnect(self) -> None: ...
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> str: ...
    def unsubscribe(self, subscription_id: str) -> bool: ...
    def publish(self, topic: str, event: dict) -> bool: ...
```

### 4. Webhook Handlers

Handle incoming webhooks from external services.

```python
class MyWebhookHandler(WebhookHandler):
    @property
    def event_type(self) -> str: return "my-event"

    def verify(self, payload: bytes, signature: str, headers: dict) -> bool: ...
    def handle(self, payload: dict, headers: dict) -> dict: ...
```

## Extension Lifecycle

1. **Discovery** — On startup, RIFT scans `extensions/` for `manifest.json`
2. **Validation** — Manifest validated against schema, dependencies checked
3. **Loading** — Entry point module imported, plugin class instantiated
3. **Registration** — Plugin registered with ExtensionManager
4. **Availability** — Plugin available via `extension_manager.get_all("domain")` etc.

## Configuration

Extensions can define `config.schema.json`:

```json
{
  "type": "object",
  "properties": {
    "api_endpoint": {"type": "string", "format": "uri"},
    "api_key": {"type": "string"},
    "poll_interval": {"type": "integer", "minimum": 1000}
  },
  "required": ["api_endpoint", "api_key"]
}
```

Config is passed to plugin's `create_scenario(config)` or `connect(config)`.

## Best Practices

1. **Fail-closed** — Validate all inputs, reject unknown fields
2. **Deterministic** — No hidden state, same input = same output
3. **Observable** — Emit structured logs, metrics, traces
4. **Versioned** — Semantic version in manifest, declare `rift_version` constraint
5. **Tested** — Unit tests for plugin logic, integration tests with RIFT core
6. **Documented** — README with config examples, API reference

## Testing Extensions

```bash
# Run extension tests
python -m pytest extensions/my-domain/tests/

# Validate manifest
python -c "from rift.developer.plugin_sdk import ExtensionManifest; ExtensionManifest.from_dict(json.load(open('extensions/my-domain/manifest.json'))).validate()"
```

## Publishing Extensions

1. Create GitHub repo: `rift-extension-{name}`
2. Add `rift-extension` topic
3. Include manifest, entry point, config schema, tests, README
4. Tag releases with semantic versioning
5. Submit to RIFT extension registry (future)

## Example: Complete Domain Extension

See `extensions/smart-building/` and `src/rift/domains/traffic/` for complete reference implementations.