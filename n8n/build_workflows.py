#!/usr/bin/env python3
"""
Generates the importable n8n workflows from their tested sources:
  ../sql/*.sql, gateway_engine.js, client_ip.js, build_error.js
Run:  python3 n8n/build_workflows.py
Never hand-edit the generated *.workflow.json -- edit the sources and rebuild.
"""
import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent
SQL = HERE.parent / "sql"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def nid(workflow, name):
    return str(uuid.uuid5(NS, f"{workflow}/{name}"))


def read(path):
    return Path(path).read_text(encoding="utf-8").strip()


def webhook(wf, name, method, path, pos):
    return {
        "parameters": {"httpMethod": method, "path": path, "responseMode": "responseNode", "options": {}},
        "id": nid(wf, name), "name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2,
        "position": pos, "webhookId": nid(wf, name + "-hook"),
    }


def code(wf, name, js, pos):
    return {"parameters": {"jsCode": js}, "id": nid(wf, name), "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


def respond(wf, name, body, pos, status=None):
    options = {"responseCode": status} if status else {}
    if status is None:
        options = {"responseCode": "={{ $json.statusCode || 200 }}"}
    return {"parameters": {"respondWith": "json", "responseBody": body, "options": options},
            "id": nid(wf, name), "name": name, "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1, "position": pos}


def postgres(wf, name, query, replacement, pos):
    return {"parameters": {"operation": "executeQuery", "query": query,
                           "options": {"queryReplacement": replacement}},
            "id": nid(wf, name), "name": name, "type": "n8n-nodes-base.postgres", "typeVersion": 2.5,
            "position": pos, "onError": "continueErrorOutput"}


def if_node(wf, name, conditions, pos):
    return {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "",
                                                       "typeValidation": "loose", "version": 1},
                                          "conditions": conditions, "combinator": "and"},
                           "options": {}},
            "id": nid(wf, name), "name": name, "type": "n8n-nodes-base.if", "typeVersion": 2, "position": pos}


def cond(i, left, op_type, op, right="", single=False):
    operator = {"type": op_type, "operation": op}
    if single:
        operator["singleValue"] = True
    return {"id": f"c{i}", "leftValue": left, "rightValue": right, "operator": operator}


def link(target, index=0):
    return {"node": target, "type": "main", "index": index}


def workflow(name, nodes, connections):
    return {"name": name, "nodes": nodes, "connections": connections, "pinData": {},
            "settings": {"executionOrder": "v1",
                         # Don't keep successful runs: they contain users' prompts and answers.
                         "saveDataSuccessExecution": "none", "saveDataErrorExecution": "all",
                         "saveManualExecutions": True, "executionTimeout": 90}}


UNAVAILABLE = ('={{ { "error": "service_unavailable", '
               '"message": "key service temporarily unavailable, please retry shortly" } }}')


def gateway():
    wf = "gateway"
    nodes = [
        webhook(wf, "Webhook", "POST", "baalebos-ai", [-900, 100]),
        if_node(wf, "Is Master Key?", [
            cond(1, "={{ $json.headers['x-api-key'] }}", "string", "equals", "={{ $env.GATEWAY_API_KEY }}"),
            cond(2, "={{ $json.headers['x-api-key'] }}", "string", "notEmpty", "", single=True),
        ], [-660, 100]),
        postgres(wf, "Check Key And Quota", read(SQL / "check_key_and_quota.sql"),
                 "={{ [ $json.headers['x-api-key'] || '', $env.PUBLIC_DAILY_CAP || '5000' ] }}", [-420, 260]),
        if_node(wf, "Allowed?", [cond(1, "={{ $json.allowed }}", "number", "gt", 0)], [-180, 260]),
        code(wf, "Build Error", read(HERE / "build_error.js"), [60, 360]),
        code(wf, "Gateway Engine", read(HERE / "gateway_engine.js"), [60, 0]),
        respond(wf, "Respond", "={{ $json }}", [320, 180]),
        respond(wf, "Respond 503", UNAVAILABLE, [-180, 480], status=503),
    ]
    conns = {
        "Webhook": {"main": [[link("Is Master Key?")]]},
        "Is Master Key?": {"main": [[link("Gateway Engine")], [link("Check Key And Quota")]]},
        "Check Key And Quota": {"main": [[link("Allowed?")], [link("Respond 503")]]},
        "Allowed?": {"main": [[link("Gateway Engine")], [link("Build Error")]]},
        "Build Error": {"main": [[link("Respond")]]},
        "Gateway Engine": {"main": [[link("Respond")]]},
    }
    return workflow("Baalebos AI Gateway", nodes, conns)


def signup():
    wf = "signup"
    nodes = [
        webhook(wf, "Webhook", "POST", "baalebos-ai-signup", [-700, 100]),
        code(wf, "Client IP", read(HERE / "client_ip.js"), [-480, 100]),
        postgres(wf, "Create Key", read(SQL / "create_key.sql"),
                 "={{ [ $json.ip, $env.SIGNUPS_PER_IP_PER_DAY || '10', $env.IP_HASH_SALT || 'baalebos' ] }}",
                 [-260, 100]),
        if_node(wf, "Got Key?",
                [cond(1, "={{ $json.api_key }}", "string", "notEmpty", "", single=True)], [-20, 100]),
        respond(wf, "Respond Key", '={{ { "api_key": $json.api_key } }}', [240, 20], status=200),
        respond(wf, "Respond Limited",
                '={{ { "error": "too_many_signups", "message": "too many keys requested from this network '
                'today; try again tomorrow, or set BAALEBOS_API_KEY if you already have one" } }}',
                [240, 200], status=429),
        respond(wf, "Respond 503", UNAVAILABLE, [-20, 320], status=503),
    ]
    conns = {
        "Webhook": {"main": [[link("Client IP")]]},
        "Client IP": {"main": [[link("Create Key")]]},
        "Create Key": {"main": [[link("Got Key?")], [link("Respond 503")]]},
        "Got Key?": {"main": [[link("Respond Key")], [link("Respond Limited")]]},
    }
    return workflow("Baalebos AI Signup", nodes, conns)


def health():
    wf = "health"
    nodes = [
        webhook(wf, "Webhook", "GET", "baalebos-ai-health", [0, 0]),
        respond(wf, "Respond", '={{ { "status": "ok", "service": "baalebos-ai" } }}', [240, 0], status=200),
    ]
    return workflow("Baalebos AI Health", nodes, {"Webhook": {"main": [[link("Respond")]]}})


def build():
    return {
        "gateway.workflow.json": gateway(),
        "signup.workflow.json": signup(),
        "health.workflow.json": health(),
    }


if __name__ == "__main__":
    for filename, wf in build().items():
        (HERE / filename).write_text(json.dumps(wf, indent=2) + "\n", encoding="utf-8")
        print(f"wrote n8n/{filename}  ({len(wf['nodes'])} nodes)")
