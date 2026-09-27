"""One-shot mechanical split of src/rift/api.py into an api/ package.

Preserves exact runtime behavior:
- route blocks move verbatim (self -> h), dispatch order unchanged
- every bare `return` (== "handled, stop dispatching") becomes `return True`
- shape-guard misses fall through via trailing `return False`
- all free names mapped to explicit imports; unknown names abort loudly
"""
import ast
import os
import re

SRC = r'C:\Users\wagde\RIFT\src\rift\api.py'
PKG = r'C:\Users\wagde\RIFT\src\rift\routes'
METHOD = {'GET': 'do_GET', 'POST': 'do_POST'}

with open(SRC, newline='') as f:
    raw = f.read()
lines = raw.split('\n')
# strip trailing \r artifacts of CRLF for uniform handling; we write LF
lines = [l[:-1] if l.endswith('\r') else l for l in lines]


def find(pat, start=0):
    for i in range(start, len(lines)):
        if re.match(pat, lines[i]):
            return i
    raise AssertionError('not found: ' + pat)


class_start = find(r'class Handler')
do_get = find(r'    def do_GET', class_start)
do_post = find(r'    def do_POST', class_start)
do_put = find(r'    def do_PUT', class_start)


def method_body(start):
    end = len(lines)
    for pat in (r'    def do_GET', r'    def do_POST', r'    def do_PUT',
                r'    def do_DELETE', r'    def do_PATCH', r'    def log_message'):
        try:
            j = find(pat, start + 1)
            end = min(end, j)
        except AssertionError:
            pass
    return start, end


_, do_get_end = method_body(do_get)
_, do_post_end = method_body(do_post)


def split_routes(start, end):
    """Split a do_* body into (preamble, [(cond, [lines])], tail).

    AST-precise: top-level `if` statements testing `path` are routes;
    anything else at method top level (rate-limit preamble, final 404
    tail) is preserved verbatim outside the dispatch chain.
    """
    # method source = def line + body, dedented by 4 for parsing
    src = '\n'.join('    ' + l if False else l[4:] if l.startswith('    ') else l
                    for l in lines[start:end])
    tree = ast.parse(src)
    assert isinstance(tree.body[0], ast.FunctionDef)
    fn = tree.body[0]
    # line numbers in `lines` (0-based): fn.lineno-1+start is the def line
    base = start  # lines[base] == '    def do_X...'

    def is_route(stmt):
        if not isinstance(stmt, ast.If):
            return False
        # Route guards are `if path == ...` / `if path.startswith(...)`
        # (possibly or-ed / parenthesized). Anything else (rate-limit,
        # shape guards at method level) is preamble/tail, never a route.
        seg = ast.get_source_segment('\n'.join(
            l[4:] if l.startswith('    ') else l for l in lines[start:end]), stmt.test)
        seg = (seg or '').strip().lstrip('(')
        return seg.startswith('path ==') or seg.startswith('path.startswith')

    preamble_end = None
    route_nodes = []
    tail_nodes = []
    seen_route = False
    for stmt in fn.body:
        if is_route(stmt):
            seen_route = True
            route_nodes.append(stmt)
        elif seen_route:
            tail_nodes.append(stmt)
    # preamble: def line through last stmt before first route
    first = route_nodes[0].lineno - 1 + base  # 0-based index of first route if
    preamble = lines[start:first]
    blocks = []
    for n, stmt in enumerate(route_nodes):
        s = stmt.lineno - 1 + base
        if n + 1 < len(route_nodes):
            e = route_nodes[n + 1].lineno - 1 + base
        else:
            # last route: end before tail nodes (if any)
            e = (tail_nodes[0].lineno - 1 + base) if tail_nodes else end
        cond = lines[s].strip()
        assert re.match(r'if \(?path\b', cond), f'expected route at {s+1}'
        blocks.append((cond, lines[s:e]))
    tail = []
    if tail_nodes:
        tail = lines[tail_nodes[0].lineno - 1 + base:end]
        # Keep only code lines: drop blanks and section-divider comments
        # (e.g. `# -- POST ---`) which belong to neither method.
        tail = [l for l in tail if l.strip() and not l.strip().startswith('#')]
    return preamble, blocks, tail


get_pre, get_blocks, get_tail = split_routes(do_get, do_get_end)
post_pre, post_blocks, post_tail = split_routes(do_post, do_post_end)
# Guard: refuse to re-run on an already-rewired api.py
assert (len(get_blocks), len(post_blocks)) == (36, 19), 'route count changed; abort'
print(f'GET routes: {len(get_blocks)}, POST routes: {len(post_blocks)}')
print(f'GET tail: {len(get_tail)} lines, POST tail: {len(post_tail)} lines')
for t in get_tail + post_tail:
    if t.strip():
        print('  tail:', t.strip()[:80])


def fn_name(method, cond):
    lits = re.findall(r'"([^"]+)"', cond)
    base = '_'.join(l.strip('/').replace('/', '_') for l in lits) or 'root'
    base = re.sub(r'[^a-z0-9]+', '_', base.lower()).strip('_')
    return f"{method.lower()}_{base}"


seen = set()

def unique(name):
    n, c = name, 2
    while n in seen:
        n = f'{name}_{c}'
        c += 1
    seen.add(n)
    return n


# module assignment by condition substring (ordered)
def assign(cond):
    c = cond
    if '/api/operations' in c:
        return 'routes_operations'
    if '/api/experiments' in c or '/api/runs' in c:
        return 'routes_experiments'
    if '/api/billing' in c:
        return 'routes_billing'
    if '/api/twin' in c or '/api/explainability' in c or '/api/intelligence' in c:
        return 'routes_twin'
    if '/api/auth' in c:
        return 'routes_auth'
    return 'routes_core'


IMPORT_MAP = {
    'json': 'import json',
    'uuid': 'import uuid',
    'os': 'import os',
    'time': 'import time',
    'datetime': 'from datetime import datetime, timezone',
    'timezone': 'from datetime import datetime, timezone',
    'Path': 'from pathlib import Path',
    'ENGINE_VERSION': 'from rift import __version__ as ENGINE_VERSION',
    'owner_mismatch': 'from rift.auth import owner_mismatch',
    'require_user_id_enforced': 'from rift.auth import require_user_id_enforced',
    'service_token_configured': 'from rift.auth import service_token_configured',
    'extract_bearer': 'from rift.auth import extract_bearer',
    'SupabaseStore': 'from rift.supabase_store import SupabaseStore',
    'log_event': 'from rift.observability import log_event',
    'Timer': 'from rift.observability import Timer',
    'new_request_id': 'from rift.observability import new_request_id',
    'describe_limits': 'from rift.limits import describe_limits',
    'SCENARIO_BOUNDS': 'from rift.limits import SCENARIO_BOUNDS',
    'MAX_PAYLOAD_BYTES': 'from rift.limits import MAX_PAYLOAD_BYTES',
    'validate_spec_payload': 'from rift.experiments import validate_spec_payload',
    'validate_run_payload': 'from rift.experiments import validate_run_payload',
    'run_spec': 'from rift.runner import run_spec',
    'billing_status': 'from rift.settings import billing_status, get_billing_config, supabase_status',
    'get_billing_config': 'from rift.settings import billing_status, get_billing_config, supabase_status',
    'supabase_status': 'from rift.settings import billing_status, get_billing_config, supabase_status',
    'BillingNotConfigured': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'CheckoutRequest': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'LemonSqueezyProvider': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'billing_idempotency_key': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'is_entitled': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'parse_webhook_event': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'verify_webhook_signature': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
    'webhook_event_id': 'from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)',
}


def transform(cond, block, method, fname):
    out = [f'def {fname}(h, request_id, timer, path, query):',
           f'    """Route {cond} (moved verbatim from api.py do_{method})."""']
    for ln in block[1:]:  # drop the `if` line; dispatch holds the condition
        if ln.strip() == '':
            out.append('')
            continue
        assert ln.startswith('        '), f'bad indent in {fname}: {ln[:50]!r}'
        code = ln[8:]  # route bodies sit 8 deep under do_*; module fn needs 4
        code = re.sub(r'\bself\b', 'h', code)
        out.append(code)
    fixed = []
    for ln in out:
        m = re.match(r'^(\s*)return\s*$', ln)
        if m:
            # Every bare `return` in the original means "handled, stop
            # dispatching": preserve indent, report True.
            fixed.append(f'{m.group(1)}return True')
        else:
            fixed.append(ln)
    fixed.append('    return False')
    text = '\n'.join(fixed)
    assert 'self' not in re.findall(r'\bself\b', text), f'self remains in {fname}'
    # Rewrite lazy relative imports (from .x -> from rift.x) by AST line
    # numbers so strings/comments are untouched.
    try:
        tree = ast.parse(text)
    except SyntaxError:
        print(f'=== SYNTAX FAIL in {fname} ===')
        print(text[:1500])
        raise
    rel_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.level or 0) > 0:
            rel_lines.add(node.lineno)
    rebuilt = []
    for i, ln in enumerate(fixed, 1):
        if i in rel_lines:
            new_ln, n = re.subn(r'^(\s*)from \.+', r'\1from rift.', ln, count=1)
            assert n == 1, f'rewrite failed in {fname}: {ln!r}'
            # 'from rift.' + 'experiments import ...' needs the module path:
            # original `from .experiments` -> `from rift.experiments`
            ln = new_ln
        rebuilt.append(ln)
    text = '\n'.join(rebuilt)
    assert 'from rift. import' not in text, f'broken relative import in {fname}'
    try:
        ast.parse(text)  # must stay valid syntax
    except SyntaxError:
        print(f'=== SYNTAX FAIL in {fname} ===')
        print(text[:2000])
        raise
    return text


def free_names(text):
    tree = ast.parse(text)
    bound = set()

    def bind_target(t):
        for n in ast.walk(t):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                bound.add(n.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            bound.add(node.name) if hasattr(node, 'name') else None
            for a in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
                bound.add(a.arg)
            if node.args.vararg:
                bound.add(node.args.vararg.arg)
            if node.args.kwarg:
                bound.add(node.args.kwarg.arg)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind_target(node.target)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                bound.add(node.name)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    bind_target(item.optional_vars)
        elif isinstance(node, ast.NamedExpr):
            bind_target(node.target)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                bound.add(a.asname or a.name.split('.')[0])
        elif isinstance(node, ast.Import):
            for a in node.names:
                bound.add((a.asname or a.name).split('.')[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            bind_target(node.targets[0] if isinstance(node, ast.Assign) else node.target)
        elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp,
                                ast.DictComp)):
            for gen in node.generators:
                bind_target(gen.target)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
    import builtins
    return used - bound - set(dir(builtins)) - {'True', 'False', 'None'}


LOCAL_SUPPORT = {'_publish_event', '_resolve_experiment', '_resolve_run',
                 '_mirror_experiment_to_archive', '_mirror_run_to_archive',
                 '_spec_from_experiment_row', '_run_from_row', '_cors_headers',
                 '_ClientGone', 'FRONTEND_DIST', '_seen_webhook_key',
                 '_remember_webhook_key', '_apply_subscription_update',
                 '_is_valid_uuid', '_client_ip', 'PERTURBATIONS',
                 'POLICY_VARIABLES', 'scenario_payload', 'configured_scenario',
                 '_bounded_float'}

modules = {}
dispatch_get, dispatch_post = [], []

for method, blocks in (('GET', get_blocks), ('POST', post_blocks)):
    for cond, block in blocks:
        # nested defs would break the transform; abort loudly
        inner = [l for l in block[1:] if re.match(r'            def ', l)]
        assert not inner, f'nested def in {cond}'
        fname = unique(fn_name(method, cond))
        mod = assign(cond)
        text = transform(cond, block, method, fname)
        # drop trailing `return False` if block cannot fall through?
        # keep uniformly: harmless and preserves shape-guard fallthrough.
        modules.setdefault(mod, []).append((fname, cond, text, block))
        body_cond = cond[3:]
        assert body_cond.endswith(':'), f'no trailing colon: {cond}'
        body_cond = body_cond[:-1]
        disp = (f'        if {body_cond}:\n'
                f'            if {mod}.{fname}(self, request_id, timer, path, query):\n'
                f'                return')
        (dispatch_get if method == 'GET' else dispatch_post).append(disp)

# free-name analysis per module (detailed pass runs later as route_need)
for mod, fns in modules.items():
    need = set()
    for fname, cond, text, block in fns:
        for name in free_names(text):
            if name in ('h', 'request_id', 'timer', 'path', 'query'):
                continue
            need.add(name)
    unknown = need - set(IMPORT_MAP) - LOCAL_SUPPORT
    assert not unknown, f'{mod} unknown names: {sorted(unknown)}'
    print(f'{mod}: {len(fns)} routes, imports: {sorted(need)}')

# ---- behavior-preservation audits on every extracted handler ----
import io
import tokenize

for mod, fns in modules.items():
    for fname, cond, text, block in fns:
        t = ast.parse(text)
        for node in ast.walk(t):
            if isinstance(node, ast.Return):
                ok = (node.value is not None and isinstance(node.value, ast.Constant)
                      and node.value.value in (True, False))
                assert ok, f'non-bool return in {fname}'
            assert not isinstance(node, (ast.Yield, ast.YieldFrom, ast.Global,
                                         ast.Nonlocal)), f'bad node in {fname}'
        # self->h rewrite must never touch string literals or comments
        for ln in block:
            try:
                toks = list(tokenize.generate_tokens(io.StringIO(ln).readline))
            except tokenize.TokenError:
                continue  # multiline string continuation; checked at def level below
            for tok in toks:
                if tok.type == tokenize.STRING and re.search(r'\bself\b', tok.string):
                    raise AssertionError(f'self inside string in {fname}: {ln.strip()!r}')
                if tok.type == tokenize.COMMENT and re.search(r'\bself\b', tok.string):
                    print(f'WARN comment mentions self in {fname}: {ln.strip()!r}')
print('audits passed: returns bool-only, no yield/global, strings untouched')

# ---- per-module needs (store block alongside for audits) ----
route_need = {}
for mod, fns in modules.items():
    need = set()
    for fname, cond, text, block in fns:
        for name in free_names(text):
            if name in ('h', 'request_id', 'timer', 'path', 'query'):
                continue
            need.add(name)
    route_need[mod] = need
    unknown = need - set(IMPORT_MAP) - LOCAL_SUPPORT
    assert not unknown, f'{mod} unknown names: {sorted(unknown)}'
    print(f'{mod}: {len(fns)} routes, imports: {sorted(need)}')

# ---- support.py via transitive closure over api.py head ----
api_tree = ast.parse(raw)
head_nodes = [n for n in api_tree.body if (n.lineno - 1) < class_start]


def abs_stmt(stmt_src):
    if re.match(r'\s*from \. import ', stmt_src):
        m = re.match(r'\s*from \. import (.*)', stmt_src)
        return f'from rift import {m.group(1)}'
    new_src, n = re.subn(r'^(\s*)from \.+', r'\1from rift.', stmt_src, count=1)
    assert n == 1, f'rewrite failed: {stmt_src!r}'
    assert 'from rift. import' not in new_src, f'broken: {new_src!r}'
    return new_src


# provider map: name -> ('import', abs_stmt) | ('node', ast_node)
providers = {}
for node in head_nodes:
    seg = ast.get_source_segment(raw, node).replace('\r', '')
    assert seg, f'no segment for {ast.dump(node)[:80]}'
    if isinstance(node, ast.ImportFrom):
        for a in node.names:
            providers[a.asname or a.name.split('.')[0]] = ('import', abs_stmt(seg))
    elif isinstance(node, ast.Import):
        for a in node.names:
            providers[(a.asname or a.name).split('.')[0]] = ('import', abs_stmt(seg))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        providers[node.name] = ('node', node)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in tgts:
            for n in ast.walk(t):
                if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                    providers[n.id] = ('node', node)

import builtins as _bi
BUILTINS = set(dir(_bi)) | {'True', 'False', 'None'}

have_def = {}      # name -> ast node (pulled verbatim from api.py)
have_import = {}   # name -> abs import stmt
pending = sorted({n for need in route_need.values() for n in need} & LOCAL_SUPPORT)
while pending:
    n = pending.pop()
    if n in have_def or n in have_import or n in IMPORT_MAP:
        continue
    assert n in providers, f'no provider in api.py head for {n}'
    kind, val = providers[n]
    if kind == 'import':
        have_import[n] = val
    else:
        have_def[n] = val
        seg = ast.get_source_segment(raw, val).replace('\r', '')
        for dep in free_names(seg):
            if dep not in have_def and dep not in have_import and dep not in IMPORT_MAP \
                    and dep not in BUILTINS:
                pending.append(dep)
print(f'support defs ({len(have_def)}): {sorted(have_def)}')
print(f'support extra imports ({len(set(have_import.values()))}):')
for s in sorted(set(have_import.values())):
    print('   ', s)

support_names = set(have_def) | set(have_import)
for mod, need in route_need.items():
    missing = (need - set(IMPORT_MAP)) - support_names
    assert not missing, f'{mod} needs {sorted(missing)} not in support'

# ---- write package ----
import shutil
if os.path.isdir(r'C:\Users\wagde\RIFT\src\rift\api'):
    shutil.rmtree(r'C:\Users\wagde\RIFT\src\rift\api')
    print('removed stale src/rift/api/ (wrong location; package is rift.routes)')
os.makedirs(PKG, exist_ok=True)
with open(os.path.join(PKG, '__init__.py'), 'w', newline='') as f:
    f.write('"""RIFT HTTP route handlers (split verbatim from rift.api; see README)."""\n')

sup_lines = ['"""Shared helpers for route handlers (moved verbatim from rift.api).',
             '',
             'Single home for module-level helpers/constants the handlers need.',
             'rift.api re-exports what it still uses; no state is duplicated.',
             '"""',
             'from __future__ import annotations', '']
for s in sorted(set(have_import.values())):
    sup_lines.append(s)
for name in sorted(have_def, key=lambda n: have_def[n].lineno):
    sup_lines.append('')
    sup_lines.append('')
    sup_lines.append(ast.get_source_segment(raw, have_def[name]).replace('\r', '').rstrip())
with open(os.path.join(PKG, 'support.py'), 'w', newline='') as f:
    f.write('\n'.join(sup_lines) + '\n')

for mod, fns in modules.items():
    need = route_need[mod]
    support = sorted(n for n in need if n not in IMPORT_MAP)
    ext = sorted(n for n in need if n in IMPORT_MAP)
    head = ['"""Route handlers (split verbatim from api.py; see package README)."""',
            'from __future__ import annotations', '']
    if support:
        head.append(f"from .support import {', '.join(support)}")
    for n in ext:
        if IMPORT_MAP[n] not in head:
            head.append(IMPORT_MAP[n])
    body = '\n\n\n'.join([t for _, _, t, _ in fns])
    with open(os.path.join(PKG, mod + '.py'), 'w', newline='') as f:
        f.write('\n'.join(head) + '\n\n\n' + body + '\n')
print('modules written:', sorted(modules))

# ---- rewire api.py: drop moved defs, dispatch to package ----
moved_ranges = sorted({(have_def[n].lineno - 1, have_def[n].end_lineno) for n in have_def},
                      reverse=True)
new_lines = list(lines)
for a, b in moved_ranges:
    # sanity: range must lie entirely before `class Handler`
    assert b <= class_start, f'moved range {a+1}-{b} past class Handler'
    del new_lines[a:b]


def refind(pat, start=0):
    for i in range(start, len(new_lines)):
        if re.match(pat, new_lines[i]):
            return i
    raise AssertionError('not found after delete: ' + pat)


def method_end(start):
    end = len(new_lines)
    for pat in (r'    def do_GET', r'    def do_POST', r'    def do_PUT',
                r'    def do_DELETE', r'    def do_PATCH', r'    def log_message'):
        try:
            end = min(end, refind(pat, start + 1))
        except AssertionError:
            pass
    return end


g2 = refind(r'    def do_GET')
g2e = method_end(g2)
p2 = refind(r'    def do_POST')
p2e = method_end(p2)
new_get = [new_lines[g2]] + get_pre[1:] + dispatch_get + get_tail
new_post = [new_lines[p2]] + post_pre[1:] + dispatch_post + post_tail
new_lines[g2:g2e] = new_get
# do_POST shifted by the GET replacement; re-find
p2 = refind(r'    def do_POST')
p2e = method_end(p2)
new_lines[p2:p2e] = [new_lines[p2]] + post_pre[1:] + dispatch_post + post_tail

new_text = '\n'.join(new_lines)
t = ast.parse(new_text)  # rewired api.py must parse
loads = {n.id for n in ast.walk(t)
         if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
stores = {n.id for n in ast.walk(t)
          if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
need_support = sorted((loads & support_names))
shadowed = sorted((loads & support_names) & stores)
print('re-export from support:', need_support)
print('shadow-check (must be empty):', shadowed)
assert not shadowed, f'support names rebound in api.py: {shadowed}'

# insert package imports after the last head import before class Handler
t2 = ast.parse(new_text)
cls_idx = next(n.lineno - 1 for n in t2.body if isinstance(n, ast.ClassDef))
last_imp = max(n.end_lineno for n in t2.body
               if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno - 1 < cls_idx)
ins = [f'from .routes import {", ".join(sorted(modules))}']
if need_support:
    ins.append(f'from .routes.support import {", ".join(need_support)}')
final_lines = new_text.split('\n')
final_lines[last_imp:last_imp] = [''] + ins + ['']
final_text = '\n'.join(final_lines)
ast.parse(final_text)
with open(SRC, 'w', newline='') as f:
    f.write(final_text.replace('\n', '\r\n'))
print('api.py rewired: do_GET/do_POST dispatch to rift.routes; '
      f'{len(moved_ranges)} top-level defs moved, {len(need_support)} re-exported')

# ---- compile-check everything written ----
import py_compile
for mod in list(modules) + ['support']:
    py_compile.compile(os.path.join(PKG, mod + '.py'), doraise=True)
py_compile.compile(SRC, doraise=True)
print('compile-check OK')
