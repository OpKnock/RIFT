"""Plugin SDK for RIFT: domain plugins, adapters, extensions (Phase 14)."""
from __future__ import annotations

import abc
import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

from ..models import Scenario, Constraint
from ..counterfactual import Future, generate_futures
from ..robust import rank_robust_candidates
from ..adversarial import search_failure_states
from ..verifier import verify_under_perturbations

T = TypeVar("T")


# --- Extension Manifest ---

@dataclass(frozen=True)
class ExtensionManifest:
    """Manifest for a RIFT extension."""
    id: str
    name: str
    version: str  # semantic version
    description: str
    author: str
    license: str = "AGPL-3.0-or-later"
    rift_version: str = ">=1.0.0"
    dependencies: dict[str, str] = field(default_factory=dict)  # extension_id -> version
    entry_point: str = "extension.py"
    config_schema: dict = field(default_factory=dict)
    provides: list[str] = field(default_factory=list)  # "domain", "optimizer", "data_source", "event_adapter", "webhook"
    entry_points: dict[str, str] = field(default_factory=dict)  # type -> class path

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "rift_version": self.rift_version,
            "dependencies": self.dependencies,
            "entry_point": self.entry_point,
            "config_schema": self.config_schema,
            "provides": self.provides,
            "entry_points": self.entry_points,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtensionManifest":
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate manifest. Returns list of errors (empty if valid)."""
        errors = []
        if not self.id:
            errors.append("Missing id")
        if not self.name:
            errors.append("Missing name")
        if not self.version:
            errors.append("Missing version")
        # Check semver format
        parts = self.version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            errors.append("Version must be semantic MAJOR.MINOR.PATCH")
        if self.rift_version and not self._check_rift_version(self.rift_version):
            errors.append(f"Invalid rift_version constraint: {self.rift_version}")
        return errors

    def _check_rift_version(self, constraint: str) -> bool:
        # Simple check - in production use packaging.version
        return True


# --- Extension Manager ---

class ExtensionManager:
    """Manage extension lifecycle: load, validate, enable, disable."""

    def __init__(self, extensions_dir: Path | None = None) -> None:
        self._extensions_dir = extensions_dir or Path("./extensions")
        self._extensions_dir.mkdir(parents=True, exist_ok=True)
        self._manifests: dict[str, ExtensionManifest] = {}
        self._instances: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._load_order: list[str] = []

    def discover(self) -> list[ExtensionManifest]:
        """Discover extensions in extensions directory."""
        manifests = []
        for ext_dir in self._extensions_dir.iterdir():
            if not ext_dir.is_dir():
                continue
            manifest_file = ext_dir / "manifest.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file) as f:
                        data = json.load(f)
                    manifest = ExtensionManifest.from_dict(data)
                    errors = manifest.validate()
                    if errors:
                        print(f"Extension {ext_dir.name} validation errors: {errors}")
                        continue
                    manifests.append(manifest)
                except Exception as e:
                    print(f"Failed to load manifest from {ext_dir}: {e}")
        return manifests

    def load(self, manifest: ExtensionManifest) -> bool:
        """Load and initialize an extension."""
        with self._lock:
            if manifest.id in self._manifests:
                return False  # Already loaded

            # Check dependencies
            for dep_id, dep_version in manifest.dependencies.items():
                if dep_id not in self._manifests:
                    print(f"Missing dependency: {dep_id}@{dep_version}")
                    return False

            # Load entry point
            try:
                ext_path = self._extensions_dir / manifest.id / manifest.entry_point
                if not ext_path.exists():
                    print(f"Entry point not found: {ext_path}")
                    return False

                # Import the extension module
                import importlib.util
                spec = importlib.util.spec_from_file_location(manifest.id, ext_path)
                if not spec or not spec.loader:
                    return False
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Instantiate provided components
                instance = {}
                for provide_type, class_path in manifest.entry_points.items():
                    class_name = class_path.split(".")[-1]
                    cls = getattr(module, class_name, None)
                    if cls:
                        instance[provide_type] = cls()

                self._manifests[manifest.id] = manifest
                self._instances[manifest.id] = instance
                self._load_order.append(manifest.id)
                return True
            except Exception as e:
                print(f"Failed to load extension {manifest.id}: {e}")
                return False

    def unload(self, extension_id: str) -> bool:
        """Unload an extension."""
        with self._lock:
            if extension_id not in self._manifests:
                return False
            # Check if other extensions depend on this
            for ext_id, manifest in self._manifests.items():
                if ext_id != extension_id and extension_id in manifest.dependencies:
                    print(f"Cannot unload {extension_id}: required by {ext_id}")
                    return False
            del self._manifests[extension_id]
            del self._instances[extension_id]
            self._load_order.remove(extension_id)
            return True

    def get(self, extension_id: str, provide_type: str) -> Any | None:
        """Get a provided component from an extension."""
        with self._lock:
            instance = self._instances.get(extension_id)
            if instance:
                return instance.get(provide_type)
            return None

    def get_all(self, provide_type: str) -> list[Any]:
        """Get all components of a given type across extensions."""
        with self._lock:
            results = []
            for instance in self._instances.values():
                if provide_type in instance:
                    results.append(instance[provide_type])
            return results

    def list_loaded(self) -> list[ExtensionManifest]:
        with self._lock:
            return list(self._manifests.values())


# --- Domain Plugin ---

class DomainPlugin(abc.ABC):
    """Base class for domain plugins."""

    @property
    @abc.abstractmethod
    def domain_id(self) -> str:
        """Unique domain identifier."""
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable domain name."""
        pass

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Domain description."""
        pass

    @abc.abstractmethod
    def create_scenario(self, config: dict) -> Scenario:
        """Create a scenario from domain-specific config."""
        pass

    @abc.abstractmethod
    def get_policy_variables(self) -> list[str]:
        """Get policy variable names for this domain."""
        pass

    @abc.abstractmethod
    def get_default_perturbations(self) -> list[dict]:
        """Get default perturbations for this domain."""
        pass

    @abc.abstractmethod
    def get_constraints(self) -> list[Constraint]:
        """Get domain constraints."""
        pass

    @abc.abstractmethod
    def get_objective(self) -> Callable[[dict], float]:
        """Get objective function."""
        pass

    @abc.abstractmethod
    def get_transition(self) -> Callable[[dict, dict], dict]:
        """Get state transition function."""
        pass

    def get_interventions(self) -> dict[str, tuple[int, int]]:
        """Get available interventions (name -> (min, max))."""
        return {}

    def get_initial_state(self, config: dict) -> dict:
        """Get initial state from config."""
        return config.get("initial_state", {})

    def validate_config(self, config: dict) -> list[str]:
        """Validate domain-specific config. Returns errors."""
        return []


# --- Scenario Plugin ---

class ScenarioPlugin(abc.ABC):
    """Plugin for custom scenario types."""

    @property
    @abc.abstractmethod
    def scenario_type(self) -> str:
        pass

    @abc.abstractmethod
    def build_scenario(self, spec: dict) -> Scenario:
        pass

    @abc.abstractmethod
    def validate_spec(self, spec: dict) -> list[str]:
        pass


# --- Optimizer Plugin ---

class OptimizerPlugin(abc.ABC):
    """Plugin for custom optimizers."""

    @property
    @abc.abstractmethod
    def optimizer_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        pass

    @abc.abstractmethod
    def supports_backend(self, backend: str) -> bool:
        pass

    @abc.abstractmethod
    def optimize(self, scenario: Scenario, **kwargs) -> tuple[dict, float]:
        """Returns (assignment, energy)."""
        pass

    def get_config_schema(self) -> dict:
        return {}


# --- Data Source Adapter ---

class DataSourceAdapter(abc.ABC):
    """Adapter for external data sources."""

    @property
    @abc.abstractmethod
    def source_type(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        pass

    @abc.abstractmethod
    def connect(self, config: dict) -> bool:
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        pass

    @abc.abstractmethod
    def fetch(self, query: dict) -> list[dict]:
        pass

    @abc.abstractmethod
    def get_schema(self) -> dict:
        pass

    def health_check(self) -> dict:
        return {"status": "unknown"}


# --- Event Adapter ---

class EventAdapter(abc.ABC):
    """Adapter for event streaming."""

    @property
    @abc.abstractmethod
    def protocol(self) -> str:
        pass

    @abc.abstractmethod
    def connect(self, config: dict) -> bool:
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        pass

    @abc.abstractmethod
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> str:
        """Returns subscription ID."""
        pass

    @abc.abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        pass

    @abc.abstractmethod
    def publish(self, topic: str, event: dict) -> bool:
        pass


# --- Webhook Handler ---

class WebhookHandler(abc.ABC):
    """Handler for incoming webhooks."""

    @property
    @abc.abstractmethod
    def event_type(self) -> str:
        pass

    @abc.abstractmethod
    def verify(self, payload: bytes, signature: str, headers: dict) -> bool:
        pass

    @abc.abstractmethod
    def handle(self, payload: dict, headers: dict) -> dict:
        """Process webhook. Returns response dict."""
        pass

    def get_expected_signature_header(self) -> str:
        return "X-Signature"


# --- Extension Validation ---

def validate_extension(extension_dir: Path) -> tuple[bool, list[str]]:
    """Validate an extension directory."""
    errors = []
    manifest_file = extension_dir / "manifest.json"
    if not manifest_file.exists():
        errors.append("Missing manifest.json")
        return False, errors

    try:
        with open(manifest_file) as f:
            manifest = ExtensionManifest.from_dict(json.load(f))
        errors.extend(manifest.validate())
    except Exception as e:
        errors.append(f"Invalid manifest: {e}")

    # Check entry point exists
    if manifest.entry_point:
        if not (extension_dir / manifest.entry_point).exists():
            errors.append(f"Entry point not found: {manifest.entry_point}")

    return len(errors) == 0, errors


def check_extension_compatibility(manifest: ExtensionManifest, rift_version: str) -> tuple[bool, list[str]]:
    """Check if extension is compatible with RIFT version."""
    errors = []
    # Parse version constraint
    # In production, use packaging.version
    return True, errors


def check_extension_version_compatibility(manifest1: ExtensionManifest, manifest2: ExtensionManifest) -> tuple[bool, list[str]]:
    """Check if two extension versions are compatible."""
    errors = []
    if manifest1.id == manifest2.id:
        # Same extension, different versions
        v1 = tuple(map(int, manifest1.version.split(".")))
        v2 = tuple(map(int, manifest2.version.split(".")))
        if v1[0] != v2[0]:
            errors.append(f"Major version mismatch: {manifest1.version} vs {manifest2.version}")
    return len(errors) == 0, errors


# --- Extension Template Generator ---

def generate_extension_template(
    extension_id: str,
    name: str,
    provides: list[str],
    output_dir: Path,
) -> Path:
    """Generate a new extension template."""
    ext_dir = output_dir / extension_id
    ext_dir.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest = ExtensionManifest(
        id=extension_id,
        name=name,
        version="1.0.0",
        description=f"{name} extension for RIFT",
        author="Your Name",
        provides=provides,
        entry_points={p: f"{extension_id}.{p.capitalize()}{p[:-1] if p.endswith('s') else ''}" for p in provides},
    )
    with open(ext_dir / "manifest.json", "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    # Entry point
    entry_point = ext_dir / "extension.py"
    with open(entry_point, "w") as f:
        f.write(_generate_extension_boilerplate(provides))

    # Config schema
    if "domain" in provides:
        config_schema = {
            "type": "object",
            "properties": {
                "initial_state": {"type": "object"},
                "custom_params": {"type": "object"},
            },
        }
        with open(ext_dir / "config.schema.json", "w") as f:
            json.dump(config_schema, f, indent=2)

    # README
    with open(ext_dir / "README.md", "w") as f:
        f.write(f"# {name}\n\nRIFT extension: {extension_id}\n")

    return ext_dir


def _generate_extension_boilerplate(provides: list[str]) -> str:
    imports = []
    classes = []

    if "domain" in provides:
        imports.append("from rift.developer.plugin_sdk import DomainPlugin")
        classes.append('''
class MyDomainPlugin(DomainPlugin):
    @property
    def domain_id(self) -> str:
        return "my-domain"

    @property
    def display_name(self) -> str:
        return "My Domain"

    @property
    def description(self) -> str:
        return "Custom domain implementation"

    def create_scenario(self, config: dict) -> Scenario:
        # Implementation here
        pass

    def get_policy_variables(self) -> list[str]:
        return ["var1", "var2"]

    def get_default_perturbations(self) -> list[dict]:
        return [{{"param": 1.0}}]

    def get_constraints(self) -> list[Constraint]:
        return []

    def get_objective(self) -> Callable[[dict], float]:
        return lambda state: 0.0

    def get_transition(self) -> Callable[[dict, dict], dict]:
        return lambda state, policy: state
''')

    if "optimizer" in provides:
        imports.append("from rift.developer.plugin_sdk import OptimizerPlugin")
        classes.append('''
class MyOptimizerPlugin(OptimizerPlugin):
    @property
    def optimizer_id(self) -> str:
        return "my-optimizer"

    @property
    def display_name(self) -> str:
        return "My Optimizer"

    def supports_backend(self, backend: str) -> bool:
        return backend == "statevector-simulator"

    def optimize(self, scenario: Scenario, **kwargs) -> tuple[dict, float]:
        return ({{}}, 0.0)
''')

    boilerplate = f'''"""Extension: {extension_id}"""
from __future__ import annotations

{" ".join(imports)}
from rift.models import Scenario, Constraint
from typing import Callable

{"".join(classes)}

# Export for entry point discovery
__all__ = {[c.split("class ")[1].split("(")[0].strip() for c in classes]}
'''
    return boilerplate


# --- Example Extension: Smart Building Domain ---

SMART_BUILDING_MANIFEST = ExtensionManifest(
    id="smart-building",
    name="Smart Building Emergency",
    version="1.0.0",
    description="Smart building emergency evacuation domain",
    author="RIFT Team",
    provides=["domain"],
    entry_points={"domain": "smart_building.domain.SmartBuildingDomain"},
)

# Canonical instance
extension_manager = ExtensionManager()