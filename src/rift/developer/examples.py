"""Example generator for RIFT developer platform (Phase 14)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_all_examples(output_dir: Path) -> dict[str, Path]:
    """Generate all example files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    written = {}

    # Python examples
    written["python/basic_demo.py"] = _write_file(output_dir / "python/basic_demo.py", PYTHON_BASIC_DEMO)
    written["python/experiment_workflow.py"] = _write_file(output_dir / "python/experiment_workflow.py", PYTHON_EXPERIMENT_WORKFLOW)
    written["python/twin_monitoring.py"] = _write_file(output_dir / "python/twin_monitoring.py", PYTHON_TWIN_MONITORING)
    written["python/async_client.py"] = _write_file(output_dir / "python/async_client.py", PYTHON_ASYNC_CLIENT)
    written["python/custom_domain.py"] = _write_file(output_dir / "python/custom_domain.py", PYTHON_CUSTOM_DOMAIN)
    written["python/webhook_server.py"] = _write_file(output_dir / "python/webhook_server.py", PYTHON_WEBHOOK_SERVER)

    # TypeScript/JavaScript examples
    written["typescript/basic_usage.ts"] = _write_file(output_dir / "typescript/basic_usage.ts", TYPESCRIPT_BASIC_USAGE)
    written["typescript/react_hooks.tsx"] = _write_file(output_dir / "typescript/react_hooks.tsx", TYPESCRIPT_REACT_HOOKS)
    written["typescript/nextjs_api.ts"] = _write_file(output_dir / "typescript/nextjs_api.ts", TYPESCRIPT_NEXTJS_API)

    # cURL examples
    written["curl/health_check.sh"] = _write_file(output_dir / "curl/health_check.sh", CURL_HEALTH_CHECK)
    written["curl/run_demo.sh"] = _write_file(output_dir / "curl/run_demo.sh", CURL_RUN_DEMO)
    written["curl/experiment_crud.sh"] = _write_file(output_dir / "curl/experiment_crud.sh", CURL_EXPERIMENT_CRUD)
    written["curl/twin_monitoring.sh"] = _write_file(output_dir / "curl/twin_monitoring.sh", CURL_TWIN_MONITORING)
    written["curl/incident_management.sh"] = _write_file(output_dir / "curl/incident_management.sh", CURL_INCIDENT_MANAGEMENT)

    # Configuration examples
    written["config/development.json"] = _write_file(output_dir / "config/development.json", CONFIG_DEVELOPMENT)
    written["config/production.json"] = _write_file(output_dir / "config/production.json", CONFIG_PRODUCTION)
    written["config/docker-compose.yml"] = _write_file(output_dir / "config/docker-compose.yml", CONFIG_DOCKER_COMPOSE)

    # Extension examples
    written["extensions/smart_building_manifest.json"] = _write_file(output_dir / "extensions/smart_building_manifest.json", EXTENSION_SMART_BUILDING)
    written["extensions/my_domain/manifest.json"] = _write_file(output_dir / "extensions/my_domain/manifest.json", EXTENSION_MY_DOMAIN_MANIFEST)
    written["extensions/my_domain/extension.py"] = _write_file(output_dir / "extensions/my_domain/extension.py", EXTENSION_MY_DOMAIN_PY)

    # README
    written["README.md"] = _write_file(output_dir / "README.md", EXAMPLES_README)

    return written


def _write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# --- Python Examples ---

PYTHON_BASIC_DEMO = '''#!/usr/bin/env python3
"""Basic RIFT demo usage."""

from rift.developer.python_sdk import create_client, DemoParams

def main():
    client = create_client(base_url="http://localhost:8080")

    # Health check
    health = client.health()
    print(f"Health: {health.status} - {health.engine} v{health.version}")

    # Engine metadata
    meta = client.meta()
    print(f"Capabilities: {meta.capabilities}")
    print(f"Optimizers: {meta.optimizers}")

    # Run demo with default params
    result = client.run_demo()
    print(f"Guardian: {result.guardian['passed']}")
    print(f"Robust policies: {len(result.robust)}")

    # Run demo with custom params
    params = DemoParams(crowd=150, smoke=20, corridor_capacity=40, block_b=True)
    result = client.run_demo(params)
    print(f"Custom demo - Guardian: {result.guardian['passed']}")

    # Future tree
    print(f"Future tree nodes: {len(result.future_tree)}")

if __name__ == "__main__":
    main()
'''

PYTHON_EXPERIMENT_WORKFLOW = '''#!/usr/bin/env python3
"""Complete experiment workflow example."""

from rift.developer.python_sdk import create_client, ExperimentSpec

def main():
    client = create_client(base_url="http://localhost:8080", api_key="your-api-key")

    # 1. Create experiment spec
    spec = ExperimentSpec(
        name="robustness-comparison",
        scenario_name="smart-building-emergency",
        initial_state={"smoke": 10, "crowd": 200, "corridor_capacity": 50},
        perturbations=[
            {"smoke": 5.0},
            {"crowd": 100.0},
            {"smoke": 5.0, "crowd": 100.0},
            {"corridor_capacity": -30.0},
        ],
        policy_variables=["route_a", "route_c", "stairwell_b"],
        optimizer="exact",
        backend="statevector-simulator",
        seed=42,
        description="Compare optimizer robustness under perturbations",
    )

    # 2. Create experiment
    experiment = client.create_experiment(spec)
    print(f"Created experiment: {experiment.id}")

    # 3. Create multiple runs with different optimizers
    optimizers = ["exact", "qaoa-expectation", "qaoa-cvar"]
    run_ids = []

    for opt in optimizers:
        # Run experiment
        run = client.create_run(
            experiment_id=experiment.id,
            optimizer=opt,
            metrics={"seed": 42, "iterations": 100},
            result={},
            seed=42,
        )
        run_ids.append(run.id)
        print(f"Created run {run.id} with {opt}")

    # 4. Compare optimizers
    comparison = client.compare(
        comparison_type="optimizer",
        baseline_id=run_ids[0],
        candidate_ids=run_ids[1:],
    )
    print(f"Comparison: {comparison['summary']}")
    for metric, data in comparison["metrics"].items():
        print(f"  {metric}: baseline={data['baseline']:.4f}, candidates={data['candidates']}")

    # 4. Export experiment
    package = client.export_experiment(experiment.id)
    with open("experiment_export.json", "w") as f:
        json.dump(package, f, indent=2)
    print("Exported experiment package")

    # 5. Import experiment
    with open("experiment_export.json") as f:
        imported = client.import_experiment(json.load(f), name="imported-robustness-comparison")
    print(f"Imported as: {imported['experiment_id']}")

if __name__ == "__main__":
    main()
'''

PYTHON_TWIN_MONITORING = '''#!/usr/bin/env python3
"""Digital Twin monitoring example."""

import time
from rift.developer.python_sdk import create_client

def main():
    client = create_client(base_url="http://localhost:8080", api_key="your-api-key")

    print("Starting twin monitoring...")

    try:
        while True:
            # Get latest twin state (day 13 = latest in demo)
            twin = client.get_twin_demo(13)

            risk_pct = twin.risk.get("risk", 0) * 100
            uncertainty = twin.risk.get("uncertainty", 0) * 100
            guardian_action = twin.guardian.get("action", "UNKNOWN")

            print(f"Day {twin.day_index}: Risk={risk_pct:.1f}% +-{uncertainty:.1f}% Guardian={guardian_action}")

            # Check guardian status
            if guardian_action == "WITHHOLD":
                print("  WITHHELD - Prediction not displayed")
                for rejection in twin.guardian.get("rejections", []):
                    print(f"    REJECTION: {rejection}")
            elif guardian_action == "WARN":
                print("  WARN - Display with warnings")
                for flag in twin.guardian.get("flags", []):
                    print(f"    FLAG: {flag}")

            # Get operational monitor
            monitor = client.get_monitor()
            print(f"  Requests: {monitor.get('requests_total', 0)}, Failure rate: {monitor.get('failure_rate', 0):.3f}")

            # Sleep before next poll
            time.sleep(30)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")


if __name__ == "__main__":
    main()
'''

PYTHON_ASYNC_CLIENT = '''#!/usr/bin/env python3
"""Async client example for high-throughput workloads."""

import asyncio
from rift.developer.python_sdk import create_async_client, DemoParams

async def run_batch_demos():
    """Run multiple demos concurrently."""
    async with create_async_client(base_url="http://localhost:8080") as client:
        # Create tasks for concurrent execution
        params_list = [
            DemoParams(crowd=50 + i * 10, smoke=5 + i * 2, corridor_capacity=50 - i * 5)
            for i in range(10)
        ]

        tasks = [client.run_demo(p) for p in params_list]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            print(f"Demo {i}: Guardian={result.guardian['passed']}, Robust={len(result.robust)}")

async def run_experiment_pipeline():
    """Run experiment pipeline asynchronously."""
    async with create_async_client(base_url="http://localhost:8080", api_key="key") as client:
        # Create experiment
        experiment = await client.create_experiment({
            "name": "async-pipeline",
            "scenario_name": "smart-building-emergency",
            "optimizer": "exact",
            "seed": 42,
        })

        # Create runs concurrently
        run_tasks = [
            client.create_run(
                experiment_id=experiment.id,
                optimizer=opt,
                metrics={"seed": 42},
                result={},
                seed=42,
            )
            for opt in ["exact", "qaoa-expectation", "qaoa-cvar"]
        ]

        runs = await asyncio.gather(*run_tasks)
        run_ids = [r.id for r in runs]

        # Compare
        comparison = await client.compare("optimizer", run_ids[0], run_ids[1:])
        print(f"Comparison: {comparison['summary']}")

async def main():
    await run_batch_demos()
    await run_experiment_pipeline()

if __name__ == "__main__":
    asyncio.run(main())
'''

PYTHON_CUSTOM_DOMAIN = '''#!/usr/bin/env python3
"""Custom domain plugin example."""

from rift.developer.plugin_sdk import DomainPlugin
from rift.models import Scenario, Constraint

class TrafficOptimizationDomain(DomainPlugin):
    """Traffic flow optimization domain."""

    @property
    def domain_id(self) -> str:
        return "traffic-optimization"

    @property
    def display_name(self) -> str:
        return "Traffic Flow Optimization"

    @property
    def description(self) -> str:
        return "Optimize traffic light timing for urban corridors"

    def create_scenario(self, config: dict) -> Scenario:
        initial_state = config.get("initial_state", {
            "flow_rate": 1000,
            "queue_length": 20,
            "avg_wait_time": 45,
        })

        def transition(state: dict, policy: dict) -> dict:
            green_time = policy.get("green_time_ratio", 0.5)
            new_flow = state["flow_rate"] * (1 + 0.2 * (green_time - 0.5))
            new_queue = max(0, state["queue_length"] - 5 * green_time)
            new_wait = max(10, state["avg_wait_time"] * (1 - 0.3 * green_time))
            return {
                "flow_rate": new_flow,
                "queue_length": new_queue,
                "avg_wait_time": new_wait,
            }

        interventions = {
            "green_time_ratio": (0.3, 0.7),
            "cycle_length": (60, 120),
        }

        constraints = [
            Constraint("flow_positive", lambda s: s.get("flow_rate", 0) > 0, "Flow rate must be positive"),
            Constraint("wait_time_reasonable", lambda s: s.get("avg_wait_time", 0) < 300, "Wait time too high"),
        ]

        def objective(state: dict) -> float:
            wait = state.get("avg_wait_time", 100)
            flow = state.get("flow_rate", 1)
            return wait / 100 - flow / 2000

        return Scenario(
            name="traffic-optimization",
            initial_state=initial_state,
            interventions=interventions,
            transition=transition,
            constraints=tuple(constraints),
            objective=objective,
        )

    def get_policy_variables(self) -> list[str]:
        return ["green_time_ratio", "cycle_length"]

    def get_default_perturbations(self) -> list[dict]:
        return [
            {"flow_rate": 200},
            {"flow_rate": -150},
            {"queue_length": 15},
            {"flow_rate": 200, "queue_length": 15},
        ]

    def get_constraints(self) -> list[Constraint]:
        return []

    def get_objective(self):
        return lambda s: s.get("avg_wait_time", 100) / 100

    def get_transition(self):
        def transition(state: dict, policy: dict) -> dict:
            green_time = policy.get("green_time_ratio", 0.5)
            new_flow = state["flow_rate"] * (1 + 0.2 * (green_time - 0.5))
            new_queue = max(0, state["queue_length"] - 5 * green_time)
            new_wait = max(10, state["avg_wait_time"] * (1 - 0.3 * green_time))
            return {"flow_rate": new_flow, "queue_length": new_queue, "avg_wait_time": new_wait}
        return transition

    def get_interventions(self) -> dict[str, tuple[int, int]]:
        return {"green_time_ratio": (0, 1), "cycle_length": (0, 1)}


# Register the domain
from rift.developer.plugin_sdk import extension_manager

def register():
    domain = TrafficOptimizationDomain()
    print(f"Registered domain: {domain.domain_id}")

if __name__ == "__main__":
    register()
'''

PYTHON_WEBHOOK_SERVER = '''#!/usr/bin/env python3
"""Webhook server for RIFT billing/events."""

from flask import Flask, request, jsonify
import hmac
import hashlib
import os

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("RIFT_WEBHOOK_SECRET", "your-webhook-secret")

def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route("/webhook/billing", methods=["POST"])
def billing_webhook():
    signature = request.headers.get("X-Signature")
    if not signature or not verify_signature(request.get_data(), signature):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.get_json()
    event_type = event.get("event_name")

    print(f"Received billing event: {event_type}")

    if event_type == "subscription_created":
        customer_id = event.get("data", {}).get("customer_id")
        print(f"New subscription for customer: {customer_id}")

    elif event_type == "subscription_updated":
        status = event.get("data", {}).get("status")
        customer_id = event.get("data", {}).get("customer_id")
        print(f"Subscription {status} for customer: {customer_id}")

    elif event_type == "subscription_cancelled":
        customer_id = event.get("data", {}).get("customer_id")
        print(f"Subscription cancelled for customer: {customer_id}")

    elif event_type == "payment_failed":
        customer_id = event.get("data", {}).get("customer_id")
        print(f"Payment failed for customer: {customer_id}")

    return jsonify({"received": True})

@app.route("/webhook/operations", methods=["POST"])
def operations_webhook():
    signature = request.headers.get("X-Signature")
    if not signature or not verify_signature(request.get_data(), signature):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.get_json()
    event_type = event.get("type")

    if event_type == "incident_created":
        print(f"New incident: {event.get('title')}")

    elif event_type == "alert_firing":
        print(f"Alert firing: {event.get('alert_name')}")

    return jsonify({"received": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
'''


# --- TypeScript Examples ---

TYPESCRIPT_BASIC_USAGE = '''import { createClient, RiftClient } from '@rift/sdk';

const client = createClient({
  baseUrl: 'http://localhost:8080',
  apiKey: 'your-api-key',
});

async function main() {
  const health = await client.health();
  console.log(`Health: ${health.status} - ${health.engine} v${health.version}`);

  const meta = await client.meta();
  console.log('Capabilities:', meta.capabilities);
  console.log('Optimizers:', meta.optimizers);

  const result = await client.runDemo();
  console.log('Guardian:', result.guardian.passed);
  console.log('Robust policies:', result.robust.length);

  const customResult = await client.runDemo({
    crowd: 150,
    smoke: 20,
    corridor_capacity: 40,
    block_b: true,
  });
  console.log('Custom demo - Guardian:', customResult.guardian.passed);
}

main().catch(console.error);
'''

TYPESCRIPT_REACT_HOOKS = '''import { useExperiments, useTwinDemo, useMonitor } from '@rift/sdk/hooks';

function Dashboard() {
  const { data: experiments, isLoading: expLoading } = useExperiments();
  const { data: twin, isLoading: twinLoading } = useTwinDemo(13);
  const { data: monitor, isLoading: monLoading } = useMonitor(5000);

  if (expLoading || twinLoading || monLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="dashboard">
      <header>
        <h1>RIFT Operations Dashboard</h1>
        <div className="status">
          <span className={monitor?.failure_rate > 0.1 ? 'error' : 'ok'}>
            Failure Rate: {(monitor?.failure_rate * 100).toFixed(2)}%
          </span>
          <span>Requests: {monitor?.requests_total}</span>
        </div>
      </header>

      <section className="twin-status">
        <h2>Digital Twin (Day {twin?.day_index})</h2>
        <div className="metrics">
          <div className="metric">
            <label>Risk</label>
            <value>{(twin?.risk?.risk * 100).toFixed(1)}%</value>
          </div>
          <div className="metric">
            <label>Uncertainty</label>
            <value>±{(twin?.risk?.uncertainty * 100).toFixed(1)}%</value>
          </div>
          <div className="metric">
            <label>Guardian</label>
            <value className={twin?.guardian?.action === 'WITHHOLD' ? 'withhold' : twin?.guardian?.action === 'WARN' ? 'warn' : 'allow'}>
              {twin?.guardian?.action}
            </value>
          </div>
        </div>

        {twin?.guardian?.rejections?.map((r: string, i: number) => (
          <div key={i} className="rejection">REJECTION: {r}</div>
        ))}
        {twin?.guardian?.flags?.map((f: string, i: number) => (
          <div key={i} className="flag">FLAG: {f}</div>
        ))}
      </section>

      <section className="experiments">
        <h2>Experiments ({experiments?.length})</h2>
        <ul>
          {experiments?.map((exp: any) => (
            <li key={exp.id}>
              <strong>{exp.name}</strong> - {exp.status}
              <br />
              <small>{exp.scenario_name} | {exp.spec?.optimizer}</small>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default Dashboard;
'''

TYPESCRIPT_NEXTJS_API = '''// app/api/rift/[...slug]/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { RiftClient, RiftError } from '@rift/sdk';

const client = new RiftClient({
  baseUrl: process.env.RIFT_API_URL || 'http://localhost:8080',
  apiKey: process.env.RIFT_API_KEY,
});

export async function GET(request: NextRequest) {
  const slug = request.nextUrl.pathname.replace('/api/rift/', '');
  const searchParams = request.nextUrl.searchParams;

  try {
    let data;
    switch (slug) {
      case 'health':
        data = await client.health();
        break;
      case 'meta':
        data = await client.meta();
        break;
      case 'demo':
        data = await client.runDemo({
          crowd: Number(searchParams.get('crowd')) || undefined,
          smoke: Number(searchParams.get('smoke')) || undefined,
          corridor_capacity: Number(searchParams.get('corridor_capacity')) || undefined,
          block_b: searchParams.get('block_b') === 'true',
        });
        break;
      case 'twin':
        const day = Number(searchParams.get('day')) || 13;
        data = await client.getTwinDemo(day);
        break;
      case 'monitor':
        data = await client.getMonitor();
        break;
      default:
        return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    return NextResponse.json(data);
  } catch (error) {
    if (error instanceof RiftError) {
      return NextResponse.json(
        { error: error.message },
        { status: error.statusCode || 500 }
      );
    }
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const slug = request.nextUrl.pathname.replace('/api/rift/', '');
  const body = await request.json();

  try {
    let data;
    switch (slug) {
      case 'experiments':
        data = await client.createExperiment(body);
        break;
      case 'incidents':
        data = await client.createIncident(body);
        break;
      default:
        return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    if (error instanceof RiftError) {
      return NextResponse.json({ error: error.message }, { status: error.statusCode || 500 });
    }
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
'''


# --- cURL Examples ---

CURL_HEALTH_CHECK = '''#!/bin/bash
# Health check
curl -s http://localhost:8080/api/health | jq .

# With authentication
curl -s -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8080/api/health | jq .
'''

CURL_RUN_DEMO = '''#!/bin/bash
# Run demo with defaults
curl -s -H "Authorization: Bearer YOUR_API_KEY" "http://localhost:8080/api/demo" | jq .

# Run demo with custom parameters
curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://localhost:8080/api/demo?crowd=150&smoke=20&corridor_capacity=40&block_b=true" | jq .

# Run demo with only crowd parameter
curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://localhost:8080/api/demo?crowd=200" | jq .
'''

CURL_EXPERIMENT_CRUD = '''#!/bin/bash
API_KEY="YOUR_API_KEY"
BASE="http://localhost:8080/api"

# Create experiment
EXPERIMENT=$(curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "my-experiment",
    "scenario_name": "smart-building-emergency",
    "initial_state": {"smoke": 10, "crowd": 200, "corridor_capacity": 50},
    "perturbations": [{"smoke": 5}, {"crowd": 80}],
    "policy_variables": ["route_a", "route_c", "stairwell_b"],
    "optimizer": "exact",
    "backend": "statevector-simulator",
    "seed": 42
  }' "$BASE/experiments")

EXP_ID=$(echo $EXPERIMENT | jq -r .id)
echo "Created experiment: $EXP_ID"

# Get experiment
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/experiments/$EXP_ID" | jq .

# Create run
RUN=$(curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "optimizer": "qaoa-expectation",
    "metrics": {"iterations": 100},
    "result": {},
    "seed": 42
  }' "$BASE/experiments/$EXP_ID/runs")

RUN_ID=$(echo $RUN | jq -r .id)
echo "Created run: $RUN_ID"

# Get run
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/runs/$RUN_ID" | jq .

# List runs
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/experiments/$EXP_ID/runs" | jq .

# Create experiment version
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "spec": {"name": "v2", "optimizer": "qaoa-cvar"},
    "version": 2,
    "description": "Try QAOA-CVAR"
  }' "$BASE/experiments/$EXP_ID/versions" | jq .

# Export experiment
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/experiments/$EXP_ID/export" > experiment_export.json

# Import experiment
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d "@experiment_export.json" "$BASE/experiments/import" | jq .
'''

CURL_TWIN_MONITORING = '''#!/bin/bash
API_KEY="YOUR_API_KEY"
BASE="http://localhost:8080/api"

# Get twin demo (day 13 = latest)
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/twin/demo?t=13" | jq .

# Get twin evidence
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/twin/evidence" | jq .

# Get operational monitor
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/ops/monitor" | jq .

# Monitor loop (poll every 30 seconds)
while true; do
  echo "=== $(date) ==="
  curl -s -H "Authorization: Bearer $API_KEY" "$BASE/twin/demo?t=13" | jq '{day_index, patient_id, risk: .risk.risk, guardian: .guardian.action}'
  curl -s -H "Authorization: Bearer $API_KEY" "$BASE/ops/monitor" | jq '{requests_total, failure_rate}'
  sleep 30
done
'''

CURL_INCIDENT_MANAGEMENT = '''#!/bin/bash
API_KEY="YOUR_API_KEY"
BASE="http://localhost:8080/api"

# Create incident
INCIDENT=$(curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "type": "alert_firing",
    "severity": "high",
    "title": "Guardian reject rate spike",
    "description": "Guardian withhold rate exceeded 50% threshold",
    "trigger_alert_id": "guardian-reject-rate",
    "tags": ["guardian", "ml"]
  }' "$BASE/operations/incidents")

INC_ID=$(echo $INCIDENT | jq -r .id)
echo "Created incident: $INC_ID"

# Acknowledge incident
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"action": "acknowledge", "note": "Investigating guardian metrics"}' \
  "$BASE/operations/incidents/$INC_ID/action" | jq .

# Investigate
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"action": "investigate", "note": "Found model weight drift in cardiac-strain-v1"}' \
  "$BASE/operations/incidents/$INC_ID/action" | jq .

# Resolve
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"action": "resolve", "note": "Rolled back model to v1.0.0, reject rate normalized"}' \
  "$BASE/operations/incidents/$INC_ID/action" | jq .

# Close
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"action": "close", "note": "Issue resolved"}' \
  "$BASE/operations/incidents/$INC_ID/action" | jq .

# List incidents
curl -s -H "Authorization: Bearer $API_KEY" "$BASE/operations/incidents?status=open&severity=high" | jq .

# Create decision
DECISION=$(curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "smart-building-emergency",
    "policy": {"route_a": 1, "route_c": 0, "stairwell_b": 1},
    "proposed_by": "operator-1",
    "guardian_verdict": {"action": "ALLOW", "display_allowed": true}
  }' "$BASE/operations/decisions")

DEC_ID=$(echo $DECISION | jq -r .id)
echo "Created decision: $DEC_ID"

# Approve decision
curl -s -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"action": "accept", "note": "Approved by shift lead"}' \
  "$BASE/operations/decisions/$DEC_ID/action" | jq .
'''


# --- Configuration Examples ---

CONFIG_DEVELOPMENT = json.dumps({
    "environment": "development",
    "api": {
        "host": "0.0.0.0",
        "port": 8080,
        "debug": True,
        "rate_limit": {"requests_per_minute": 1000}
    },
    "database": {
        "url": "sqlite:///rift_dev.db",
        "echo": True
    },
    "quantum": {
        "backend": "statevector-simulator",
        "shots": 1024
    },
    "logging": {
        "level": "DEBUG",
        "format": "json",
        "output": "stdout"
    },
    "security": {
        "api_key_enabled": False,
        "jwt_enabled": False,
        "rate_limit_enabled": False
    },
    "monitoring": {
        "enabled": True,
        "metrics_port": 9090,
        "health_check_interval": 30
    }
}, indent=2)

CONFIG_PRODUCTION = json.dumps({
    "environment": "production",
    "api": {
        "host": "0.0.0.0",
        "port": 8080,
        "debug": False,
        "workers": 4,
        "rate_limit": {"requests_per_minute": 100}
    },
    "database": {
        "url": "${DATABASE_URL}",
        "pool_size": 20,
        "max_overflow": 10
    },
    "quantum": {
        "backend": "statevector-simulator",
        "ibm_token": "${IBM_QPU_TOKEN}",
        "shots": 4096
    },
    "logging": {
        "level": "INFO",
        "format": "json",
        "output": "stdout"
    },
    "security": {
        "api_key_enabled": True,
        "jwt_enabled": True,
        "rate_limit_enabled": True,
        "webhook_secret": "${WEBHOOK_SECRET}"
    },
    "monitoring": {
        "enabled": True,
        "metrics_port": 9090,
        "health_check_interval": 10,
        "prometheus_enabled": True
    },
    "billing": {
        "provider": "lemon_squeezy",
        "webhook_secret": "${LEMON_SQUEEZY_WEBHOOK_SECRET}"
    }
}, indent=2)

CONFIG_DOCKER_COMPOSE = '''version: '3.8'

services:
  rift-api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - RIFT_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/rift
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
      - LEMON_SQUEEZY_WEBHOOK_SECRET=${LEMON_SQUEEZY_WEBHOOK_SECRET}
    depends_on:
      - db
      - redis
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=rift
      - POSTGRES_USER=rift
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rift"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  redis_data:
  grafana_data:
'''


# --- Extension Examples ---

EXTENSION_SMART_BUILDING = json.dumps({
    "id": "smart-building",
    "name": "Smart Building Emergency",
    "version": "1.0.0",
    "description": "Smart building emergency evacuation domain for RIFT",
    "author": "RIFT Team",
    "license": "AGPL-3.0-or-later",
    "rift_version": ">=1.0.0",
    "dependencies": {},
    "entry_point": "smart_building/domain.py",
    "config_schema": {
        "type": "object",
        "properties": {
            "building_type": {"type": "string", "enum": ["office", "hospital", "school", "residential"]},
            "floors": {"type": "integer", "minimum": 1, "maximum": 100},
            "occupancy": {"type": "integer", "minimum": 1}
        }
    },
    "provides": ["domain"],
    "entry_points": {
        "domain": "smart_building.domain.SmartBuildingDomain"
    }
}, indent=2)

EXTENSION_MY_DOMAIN_MANIFEST = json.dumps({
    "id": "my-custom-domain",
    "name": "My Custom Domain",
    "version": "1.0.0",
    "description": "Template for a custom RIFT domain plugin",
    "author": "Your Name",
    "license": "AGPL-3.0-or-later",
    "rift_version": ">=1.0.0",
    "dependencies": {},
    "entry_point": "extension.py",
    "config_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "number"},
            "param2": {"type": "string"}
        }
    },
    "provides": ["domain"],
    "entry_points": {
        "domain": "my_domain.domain.MyDomainPlugin"
    }
}, indent=2)

EXTENSION_MY_DOMAIN_PY = '''"""My Custom Domain Plugin."""

from rift.developer.plugin_sdk import DomainPlugin
from rift.models import Scenario, Constraint
from typing import Callable

class MyDomainPlugin(DomainPlugin):
    @property
    def domain_id(self) -> str:
        return "my-custom-domain"

    @property
    def display_name(self) -> str:
        return "My Custom Domain"

    @property
    def description(self) -> str:
        return "Template for a custom RIFT domain"

    def create_scenario(self, config: dict) -> Scenario:
        initial_state = config.get("initial_state", {"value": 100})

        def transition(state: dict, policy: dict) -> dict:
            action = policy.get("action", 0)
            return {"value": max(0, state["value"] - action * 10)}

        interventions = {"action": (0, 10)}
        constraints = [Constraint("non_negative", lambda s: s.get("value", 0) >= 0, "Value must be non-negative")]

        def objective(state: dict) -> float:
            return state.get("value", 0)

        return Scenario(
            name="my-custom-domain",
            initial_state=initial_state,
            interventions=interventions,
            transition=transition,
            constraints=tuple(constraints),
            objective=objective,
        )

    def get_policy_variables(self) -> list[str]:
        return ["action"]

    def get_default_perturbations(self) -> list[dict]:
        return [{"value": 20}, {"value": -10}]

    def get_constraints(self) -> list[Constraint]:
        return []

    def get_objective(self) -> Callable[[dict], float]:
        return lambda s: s.get("value", 0)

    def get_transition(self) -> Callable[[dict, dict], dict]:
        def transition(state: dict, policy: dict) -> dict:
            action = policy.get("action", 0)
            return {"value": max(0, state["value"] - action * 10)}
        return transition

    def get_interventions(self) -> dict[str, tuple[int, int]]:
        return {"action": (0, 10)}
'''

EXAMPLES_README = '''# RIFT Examples

This directory contains runnable examples for the RIFT platform.

## Structure

```
examples/
├── python/           # Python SDK examples
├── typescript/       # TypeScript/JavaScript SDK examples
├── curl/             # cURL command examples
├── config/           # Configuration file templates
└── extensions/       # Extension/plugin examples
```

## Running Examples

### Python Examples

```bash
# Install SDK
pip install -e ../src

# Run basic demo
python python/basic_demo.py

# Run experiment workflow
python python/experiment_workflow.py

# Run twin monitoring
python python/twin_monitoring.py

# Run async client
python python/async_client.py
```

### TypeScript Examples

```bash
# Install SDK
npm install @rift/sdk zod

# Run with ts-node
npx ts-node typescript/basic_usage.ts

# Or compile and run
tsc typescript/basic_usage.ts && node basic_usage.js
```

### cURL Examples

```bash
# Make scripts executable
chmod +x curl/*.sh

# Run health check
./curl/health_check.sh

# Run demo
./curl/run_demo.sh

# Full experiment workflow
./curl/experiment_crud.sh
```

### Configuration

Copy and customize config files:

```bash
# Development
cp config/development.json ../config/development.json

# Production
cp config/production.json ../config/production.json

# Docker
cp config/docker-compose.yml ../docker-compose.yml
```

### Extensions

```bash
# View smart building extension manifest
cat extensions/smart_building_manifest.json

# Create new extension from template
python -c "
from rift.developer.plugin_sdk import generate_extension_template
from pathlib import Path
generate_extension_template('my-domain', 'My Domain', ['domain'], Path('../extensions'))
"
```

## Example Workflows

### 1. Basic Demo
Run the smart-building-emergency demo and inspect the guardian verdict.

### 2. Experiment Pipeline
Create experiment → Run multiple optimizers → Compare → Export/Import

### 3. Digital Twin Monitoring
Poll twin state, check guardian, monitor operational metrics

### 4. Incident Management
Create incident → Acknowledge → Investigate → Resolve → Close

### 5. Custom Domain
Implement DomainPlugin → Register via extension manifest → Use in experiments

## Requirements

- Python 3.11+
- Node.js 18+ (for TypeScript examples)
- RIFT API running on localhost:8080 (or configured base URL)
- API key for authenticated endpoints
'''