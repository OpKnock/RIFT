import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from .benchmark import benchmark_suite
from .counterfactual import generate_futures
from .causal import emergency_causal_graph
from .futures import branch_futures
from .models import Scenario
from .optimizer import QUBO
from .robust import rank_robust_candidates
from .scenarios import emergency_building

ROOT=Path(__file__).resolve().parents[2]/"web"

def scenario_payload(scenario:Scenario):
    perturbations=[{"smoke":2.0},{"crowd":80.0},{"smoke":2.0,"crowd":80.0},{"corridor_capacity":-70.0}]
    futures=generate_futures(scenario); ranked=rank_robust_candidates(scenario,futures,perturbations)
    q=QUBO(("route_a","route_c"),{"route_a":4.0,"route_c":2.5},{("route_a","route_c"):-1.5})
    bench=benchmark_suite(q)
    return {
      "scenario":{"name":scenario.name,"initial_state":scenario.initial_state,"interventions":{k:list(v) for k,v in scenario.interventions.items()}},
      "futures":[{"policy":f.policy,"state":f.state,"score":f.score,"valid":f.valid} for f in futures],
      "robust":[{"policy":a.candidate.policy,"score":a.candidate.score,"worst_case_score":a.worst_case.adversarial_score if a.worst_case else a.candidate.score,"robustness_gap":a.robustness_gap,"worst_perturbation":a.worst_case.perturbation if a.worst_case else {}} for a in ranked],
      "benchmark":[{"method":b.method,"energy":b.energy,"assignment":b.assignment,"runtime_ms":b.runtime_ms,"note":b.note,"probability":b.probability,"expected_energy":b.expected_energy} for b in bench],\n      "causal_graph":{"nodes":emergency_causal_graph().nodes,"edges":[{"cause":e.cause,"effect":e.effect,"strength":e.strength} for e in emergency_causal_graph().edges]},\n      "future_tree":[{"id":n.id,"parent_id":n.parent_id,"depth":n.depth,"policy":n.policy,"score":n.score,"valid":n.valid,"label":n.label} for n in branch_futures(scenario,2).nodes],
    }

def configured_scenario(query):
    s=emergency_building()
    for key in ("crowd","smoke","corridor_capacity"):
        if key in query:
            try: s.initial_state[key]=float(query[key][0])
            except (ValueError,TypeError): pass
    if query.get("block_b",["0"])[0] in ("1","true","yes"):
        s.initial_state["blocked_b_penalty"]=35.0
    return s

class Handler(BaseHTTPRequestHandler):
    def _send(self,status,data,content_type="application/json"):
        raw=data if isinstance(data,bytes) else data.encode()
        self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query)
        if path=="/api/health": return self._send(200,json.dumps({"status":"ok","engine":"rift","quantum_backend":"statevector-simulator"}))
        if path=="/api/demo": return self._send(200,json.dumps(scenario_payload(configured_scenario(query))))
        files={"/":"index.html","/index.html":"index.html","/app.js":"app.js","/styles.css":"styles.css"}
        if path in files:
            ext=Path(files[path]).suffix; ct={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8"}[ext]
            return self._send(200,(ROOT/files[path]).read_bytes(),ct)
        return self._send(404,json.dumps({"error":"not found"}))
def serve(host="127.0.0.1",port=8080): ThreadingHTTPServer((host,port),Handler).serve_forever()
