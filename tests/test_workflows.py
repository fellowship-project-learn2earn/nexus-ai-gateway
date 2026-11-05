"""The generated n8n workflows must match their tested sources and be structurally sound."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
N8N = ROOT / "n8n"
SQL = ROOT / "sql"

spec = importlib.util.spec_from_file_location("build_workflows", N8N / "build_workflows.py")
bw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bw)

BUILT = bw.build()


@pytest.mark.parametrize("filename", sorted(BUILT))
def test_committed_json_is_up_to_date(filename):
    committed = json.loads((N8N / filename).read_text())
    assert committed == BUILT[filename], f"{filename} is stale: run python3 n8n/build_workflows.py"


@pytest.mark.parametrize("filename", sorted(BUILT))
def test_connections_point_at_real_nodes(filename):
    wf = BUILT[filename]
    names = [n["name"] for n in wf["nodes"]]
    assert len(names) == len(set(names)), "duplicate node names"
    for src, outs in wf["connections"].items():
        assert src in names
        for branch in outs["main"]:
            for link in branch:
                assert link["node"] in names


@pytest.mark.parametrize("filename", sorted(BUILT))
def test_no_credentials_or_secrets_in_exports(filename):
    text = json.dumps(BUILT[filename])
    assert '"credentials"' not in text
    assert not re.search(r"(sk-|gsk_|hf_|ghp_)[A-Za-z0-9]{10,}", text)


def test_sql_is_parameterised_never_interpolated():
    for wf in BUILT.values():
        for node in wf["nodes"]:
            if node["type"] == "n8n-nodes-base.postgres":
                query = node["parameters"]["query"]
                assert "{{" not in query, f"{node['name']} interpolates values into SQL"
                assert "queryReplacement" in node["parameters"]["options"]


def test_postgres_nodes_match_the_sql_files_that_were_tested():
    gw = {n["name"]: n for n in BUILT["gateway.workflow.json"]["nodes"]}
    su = {n["name"]: n for n in BUILT["signup.workflow.json"]["nodes"]}
    assert gw["Check Key And Quota"]["parameters"]["query"] == (SQL / "check_key_and_quota.sql").read_text().strip()
    assert su["Create Key"]["parameters"]["query"] == (SQL / "create_key.sql").read_text().strip()


def test_code_nodes_match_their_source_files():
    gw = {n["name"]: n for n in BUILT["gateway.workflow.json"]["nodes"]}
    assert gw["Gateway Engine"]["parameters"]["jsCode"] == (N8N / "gateway_engine.js").read_text().strip()
    assert gw["Build Error"]["parameters"]["jsCode"] == (N8N / "build_error.js").read_text().strip()


def test_parameter_counts_line_up():
    gw = {n["name"]: n for n in BUILT["gateway.workflow.json"]["nodes"]}
    su = {n["name"]: n for n in BUILT["signup.workflow.json"]["nodes"]}

    def highest(q):
        return max(int(m) for m in re.findall(r"\$(\d+)", q))

    assert highest(gw["Check Key And Quota"]["parameters"]["query"]) == 2
    assert highest(su["Create Key"]["parameters"]["query"]) == 3


def test_master_key_check_refuses_an_empty_header():
    """If GATEWAY_API_KEY were ever unset, an empty header must not match it."""
    ifn = next(n for n in BUILT["gateway.workflow.json"]["nodes"] if n["name"] == "Is Master Key?")
    ops = [c["operator"]["operation"] for c in ifn["parameters"]["conditions"]["conditions"]]
    assert "notEmpty" in ops and ifn["parameters"]["conditions"]["combinator"] == "and"


def test_expressions_carry_the_leading_equals():
    """The bug that caused hours of 401s: an expression without '=' is compared as literal text."""
    for wf in BUILT.values():
        for node in wf["nodes"]:
            if node["type"] == "n8n-nodes-base.if":
                for c in node["parameters"]["conditions"]["conditions"]:
                    for side in ("leftValue", "rightValue"):
                        v = c[side]
                        if isinstance(v, str) and "{{" in v:
                            assert v.startswith("="), f"{node['name']}.{side} is missing the leading '='"


def test_database_outage_degrades_to_503_not_a_generic_error():
    for fname in ("gateway.workflow.json", "signup.workflow.json"):
        wf = BUILT[fname]
        pg = next(n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.postgres")
        assert pg["onError"] == "continueErrorOutput"
        assert wf["connections"][pg["name"]]["main"][1][0]["node"] == "Respond 503"


def test_successful_runs_are_not_stored():
    for wf in BUILT.values():
        assert wf["settings"]["saveDataSuccessExecution"] == "none"
