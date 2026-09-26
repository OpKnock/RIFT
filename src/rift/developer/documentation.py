"""Documentation generation for RIFT (Phase 14)."""
from __future__ import annotations

import json
import inspect
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class APIEndpoint:
    method: str
    path: str
    summary: str
    description: str
    parameters: list[dict] = field(default_factory=list)
    request_body: dict | None = None
    responses: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    security: list[str] = field(default_factory=list)
    deprecated: bool = False


@dataclass
class APIDocumentation:
    title: str = "RIFT API"
    version: str = "1.0.0"
    description: str = "Robust Intervention & Future Testing API"
    base_url: str = "http://localhost:8080"
    endpoints: list[APIEndpoint] = field(default_factory=list)
    schemas: dict = field(default_factory=dict)
    security_schemes: dict = field(default_factory=dict)

    def add_endpoint(self, endpoint: APIEndpoint) -> None:
        self.endpoints.append(endpoint)

    def to_openapi(self) -> dict:
        """Generate OpenAPI 3.0 spec."""
        paths = {}
        for ep in self.endpoints:
            if ep.path not in paths:
                paths[ep.path] = {}
            paths[ep.path][ep.method.lower()] = {
                "summary": ep.summary,
                "description": ep.description,
                "operationId": f"{ep.method.lower()}_{ep.path.strip('/').replace('/', '_')}",
                "tags": ep.tags,
                "parameters": ep.parameters,
                "requestBody": ep.request_body,
                "responses": ep.responses,
                "security": [{"bearerAuth": []}] if ep.security else [],
                "deprecated": ep.deprecated,
            }

        return {
            "openapi": "3.0.3",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "servers": [{"url": self.base_url, "description": "Default server"}],
            "paths": paths,
            "components": {
                "schemas": self.schemas,
                "securitySchemes": self.security_schemes,
            },
        }

    def to_markdown(self) -> str:
        """Generate Markdown documentation."""
        lines = [
            f"# {self.title} v{self.version}",
            "",
            self.description,
            "",
            f"Base URL: `{self.base_url}`",
            "",
            "## Authentication",
            "",
            "All API endpoints (except `/api/health` and `/api/meta`) require authentication via Bearer token.",
            "",
            "```bash",
            "curl -H 'Authorization: Bearer YOUR_API_KEY' {self.base_url}/api/demo",
            "```",
            "",
            "## Endpoints",
            "",
        ]

        # Group by tags
        by_tag = {}
        for ep in self.endpoints:
            for tag in ep.tags or ["default"]:
                by_tag.setdefault(tag, []).append(ep)

        for tag, endpoints in sorted(by_tag.items()):
            lines.append(f"### {tag}")
            lines.append("")
            for ep in endpoints:
                deprecated = " **DEPRECATED**" if ep.deprecated else ""
                lines.append(f"#### {ep.method} {ep.path}{deprecated}")
                lines.append("")
                lines.append(ep.description)
                lines.append("")
                if ep.parameters:
                    lines.append("**Parameters:**")
                    lines.append("")
                    lines.append("| Name | In | Required | Type | Description |")
                    lines.append("|------|----|----------|------|-------------|")
                    for p in ep.parameters:
                        required = "Yes" if p.get("required") else "No"
                        lines.append(f"| {p['name']} | {p['in']} | {required} | {p.get('schema', {}).get('type', 'string')} | {p.get('description', '')} |")
                    lines.append("")
                if ep.request_body:
                    lines.append("**Request Body:**")
                    lines.append("")
                    lines.append("```json")
                    lines.append(json.dumps(ep.request_body, indent=2))
                    lines.append("```")
                    lines.append("")
                lines.append("**Responses:**")
                lines.append("")
                for code, resp in sorted(ep.responses.items()):
                    lines.append(f"- `{code}`: {resp.get('description', '')}")
                lines.append("")

        return "\n".join(lines)

    def write_openapi(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_openapi(), indent=2))

    def write_markdown(self, path: Path) -> None:
        path.write_text(self.to_markdown())


# --- Architecture Documentation ---

@dataclass
class ArchitectureDocs:
    title: str = "RIFT Architecture"
    version: str = "1.0.0"
    overview: str = ""
    components: list[dict] = field(default_factory=list)
    data_flows: list[dict] = field(default_factory=list)
    deployment: str = ""
    security: str = ""

    def add_component(self, name: str, description: str, responsibilities: list[str], technologies: list[str], interfaces: list[str]) -> None:
        self.components.append({
            "name": name,
            "description": description,
            "responsibilities": responsibilities,
            "technologies": technologies,
            "interfaces": interfaces,
        })

    def add_data_flow(self, name: str, description: str, source: str, destination: str, data: str, protocol: str) -> None:
        self.data_flows.append({
            "name": name,
            "description": description,
            "source": source,
            "destination": destination,
            "data": data,
            "protocol": protocol,
        })

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title} v{self.version}",
            "",
            self.overview,
            "",
            "## Components",
            "",
        ]

        for comp in self.components:
            lines.append(f"### {comp['name']}")
            lines.append("")
            lines.append(comp["description"])
            lines.append("")
            if comp["responsibilities"]:
                lines.append("**Responsibilities:**")
                lines.append("")
                for r in comp["responsibilities"]:
                    lines.append(f"- {r}")
                lines.append("")
            if comp["technologies"]:
                lines.append(f"**Technologies:** {', '.join(comp['technologies'])}")
                lines.append("")
            if comp["interfaces"]:
                lines.append(f"**Interfaces:** {', '.join(comp['interfaces'])}")
                lines.append("")

        if self.data_flows:
            lines.append("## Data Flows")
            lines.append("")
            for flow in self.data_flows:
                lines.append(f"### {flow['name']}")
                lines.append("")
                lines.append(flow["description"])
                lines.append("")
                lines.append(f"- **Source:** {flow['source']}")
                lines.append(f"- **Destination:** {flow['destination']}")
                lines.append(f"- **Data:** {flow['data']}")
                lines.append(f"- **Protocol:** {flow['protocol']}")
                lines.append("")

        if self.deployment:
            lines.append("## Deployment")
            lines.append("")
            lines.append(self.deployment)
            lines.append("")

        if self.security:
            lines.append("## Security")
            lines.append("")
            lines.append(self.security)
            lines.append("")

        return "\n".join(lines)

    def write_markdown(self, path: Path) -> None:
        path.write_text(self.to_markdown())


# --- Contributor Guide ---

@dataclass
class ContributorGuide:
    title: str = "RIFT Contributor Guide"
    version: str = "1.0.0"
    sections: list[dict] = field(default_factory=list)

    def add_section(self, title: str, content: str, order: int = 0) -> None:
        self.sections.append({"title": title, "content": content, "order": order})

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title} v{self.version}",
            "",
            "Welcome to RIFT! This guide will help you contribute effectively.",
            "",
        ]

        for section in sorted(self.sections, key=lambda s: s["order"]):
            lines.append(f"## {section['title']}")
            lines.append("")
            lines.append(section["content"])
            lines.append("")

        return "\n".join(lines)

    def write_markdown(self, path: Path) -> None:
        path.write_text(self.to_markdown())


# --- Runbook Generator ---

@dataclass
class Runbook:
    title: str
    description: str
    severity: str  # critical, high, medium, low
    symptoms: list[str]
    diagnosis_steps: list[str]
    resolution_steps: list[str]
    verification_steps: list[str]
    contacts: list[str] = field(default_factory=list)
    related_runbooks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RunbookGenerator:
    runbooks: list[Runbook] = field(default_factory=list)

    def add_runbook(self, runbook: Runbook) -> None:
        self.runbooks.append(runbook)

    def generate_all(self, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for rb in self.runbooks:
            path = output_dir / f"{rb.title.lower().replace(' ', '-')}.md"
            path.write_text(rb.to_markdown())
            written.append(path)
        # Generate index
        index_path = output_dir / "index.md"
        index_path.write_text(self._generate_index())
        written.append(index_path)
        return written

    def _generate_index(self) -> str:
        lines = [
            "# Runbook Index",
            "",
            "Auto-generated from runbook definitions.",
            "",
            "| Runbook | Severity | Tags | Last Updated |",
            "|---------|----------|------|--------------|",
        ]
        for rb in sorted(self.runbooks, key=lambda r: r.severity):
            tags = ", ".join(rb.tags)
            date = rb.last_updated[:10]
            lines.append(f"| [{rb.title}]({rb.title.lower().replace(' ', '-')}.md) | {rb.severity} | {tags} | {date} |")
        return "\n".join(lines)


# Extend Runbook with markdown generation
def _runbook_to_markdown(self) -> str:
    lines = [
        f"# {self.title}",
        "",
        f"**Severity:** {self.severity}",
        f"**Last Updated:** {self.last_updated}",
        f"**Tags:** {', '.join(self.tags) if self.tags else 'none'}",
        "",
        "## Description",
        "",
        self.description,
        "",
        "## Symptoms",
        "",
    ]
    for s in self.symptoms:
        lines.append(f"- {s}")
    lines.extend([
        "",
        "## Diagnosis",
        "",
    ])
    for i, step in enumerate(self.diagnosis_steps, 1):
        lines.append(f"{i}. {step}")
    lines.extend([
        "",
        "## Resolution",
        "",
    ])
    for i, step in enumerate(self.resolution_steps, 1):
        lines.append(f"{i}. {step}")
    lines.extend([
        "",
        "## Verification",
        "",
    ])
    for i, step in enumerate(self.verification_steps, 1):
        lines.append(f"{i}. {step}")
    if self.contacts:
        lines.extend([
            "",
            "## Contacts",
            "",
        ])
        for c in self.contacts:
            lines.append(f"- {c}")
    if self.related_runbooks:
        lines.extend([
            "",
            "## Related Runbooks",
            "",
        ])
        for r in self.related_runbooks:
            lines.append(f"- {r}")
    return "\n".join(lines)

Runbook.to_markdown = _runbook_to_markdown


# --- Default Documentation ---

def generate_default_docs(output_dir: Path) -> dict[str, Path]:
    """Generate all default documentation."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # API Documentation
    api_doc = APIDocumentation()
    api_doc.add_endpoint(APIEndpoint(
        method="GET",
        path="/api/health",
        summary="Health check",
        description="Check API health status",
        tags=["health"],
        responses={"200": {"description": "Healthy"}, "503": {"description": "Unhealthy"}},
    ))
    api_doc.add_endpoint(APIEndpoint(
        method="GET",
        path="/api/meta",
        summary="Engine metadata",
        description="Get engine version, capabilities, and limits",
        tags=["meta"],
        responses={"200": {"description": "Engine metadata"}},
    ))
    api_doc.add_endpoint(APIEndpoint(
        method="GET",
        path="/api/demo",
        summary="Run demo scenario",
        description="Execute the smart-building-emergency demo with optional parameters",
        tags=["demo"],
        parameters=[
            {"name": "crowd", "in": "query", "required": False, "schema": {"type": "integer"}, "description": "Crowd level"},
            {"name": "smoke", "in": "query", "required": False, "schema": {"type": "integer"}, "description": "Smoke level"},
            {"name": "corridor_capacity", "in": "query", "required": False, "schema": {"type": "integer"}, "description": "Corridor capacity"},
            {"name": "block_b", "in": "query", "required": False, "schema": {"type": "boolean"}, "description": "Block stairwell B"},
        ],
        responses={"200": {"description": "Demo result"}, "422": {"description": "Invalid parameters"}},
    ))
    api_doc.add_endpoint(APIEndpoint(
        method="POST",
        path="/api/experiments",
        summary="Create experiment",
        description="Create a new experiment with specified configuration",
        tags=["experiments"],
        security=["bearerAuth"],
        request_body={
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ExperimentSpec"}}}
        },
        responses={"201": {"description": "Created"}, "400": {"description": "Invalid spec"}, "401": {"description": "Unauthorized"}},
    ))

    # Architecture
    arch = ArchitectureDocs()
    arch.overview = "RIFT is a modular optimization platform with a clean separation between core engine, domain models, and presentation layers."
    arch.add_component("Core Engine", "Optimization and simulation core", ["Scenario execution", "Counterfactual generation", "Robust ranking", "Guardian verification"], ["Python 3.11+", "NumPy", "SciPy"], ["Scenario API", "Optimizer interface"])
    arch.add_component("Health Domain", "Cardiac strain digital twin", ["Patient state sync", "Risk prediction", "Counterfactual trajectories", "Guardian 2.0"], ["Python", "FHIR", "PhysioNet"], ["Twin API", "Evidence API"])
    arch.add_data_flow("Demo Execution", "Run smart-building demo", "Client", "Core Engine", "Scenario config + parameters", "HTTP/JSON")
    arch.add_data_flow("Twin Update", "Synchronize patient twin", "Data Sources", "Health Domain", "Wearable/EHR observations", "Internal")
    arch.deployment = "Docker, Kubernetes, or bare metal. See deployment/ directory."
    arch.security = "JWT/API key auth, rate limiting, input validation, signed webhooks."

    # Contributor Guide
    contrib = ContributorGuide()
    contrib.add_section("Getting Started", "1. Fork the repo\n2. Create a feature branch\n3. Make changes\n4. Run tests: `python -m pytest`\n5. Submit PR", 1)
    contrib.add_section("Code Style", "Follow PEP 8. Use `ruff` for linting. Type hints required for new code.", 2)
    contrib.add_section("Testing", "All new code must have tests. Run `python -m pytest tests/` before PR.", 3)
    contrib.add_section("Documentation", "Update docs for any API changes. Run `python -m rift.developer.documentation` to regenerate.", 4)

    # Runbooks
    runbooks = RunbookGenerator()
    runbooks.add_runbook(Runbook(
        title="API Unhealthy",
        description="The /api/health endpoint returns unhealthy status",
        severity="critical",
        symptoms=["Health check fails", "Engine version mismatch", "Dependencies unavailable"],
        diagnosis_steps=[
            "Check service logs for errors",
            "Verify database connectivity",
            "Check quantum backend availability",
            "Verify config values",
        ],
        resolution_steps=[
            "Restart service if transient",
            "Fix configuration issues",
            "Scale up if resource exhaustion",
        ],
        verification_steps=["Health endpoint returns ok", "Meta endpoint returns correct version"],
        contacts=["oncall@rift.example.com"],
        tags=["api", "health"],
    ))
    runbooks.add_runbook(Runbook(
        title="High Guardian Rejection Rate",
        description="Guardian is withholding >50% of predictions",
        severity="high",
        symptoms=["Guardian reject rate alert firing", "Dashboard shows WITHHOLD status", "Clinician complaints"],
        diagnosis_steps=[
            "Check guardian verdict details in logs",
            "Verify input data quality",
            "Check model weights digest",
            "Review recent model promotions",
        ],
        resolution_steps=[
            "Investigate root cause from verdict",
            "Rollback model if weights changed unexpectedly",
            "Improve data quality if stale/missing",
        ],
        verification_steps=["Guardian reject rate returns to baseline", "Predictions display correctly"],
        contacts=["ml-team@rift.example.com"],
        tags=["guardian", "ml"],
    ))

    # Write all
    written = {}
    api_doc.write_openapi(output_dir / "openapi.json")
    api_doc.write_markdown(output_dir / "API.md")
    written["openapi.json"] = output_dir / "openapi.json"
    written["API.md"] = output_dir / "API.md"

    arch.write_markdown(output_dir / "ARCHITECTURE.md")
    written["ARCHITECTURE.md"] = output_dir / "ARCHITECTURE.md"

    contrib.write_markdown(output_dir / "CONTRIBUTING.md")
    written["CONTRIBUTING.md"] = output_dir / "CONTRIBUTING.md"

    runbooks.generate_all(output_dir / "runbooks")
    written["runbooks"] = output_dir / "runbooks"

    return written