"""Conservative node checks. Values are inspected locally and never returned."""
from __future__ import annotations

import re

from .models import AnalysisLimits, InputError, RiskFinding
from .privacy import fingerprint, is_expression


HTTP_VERSIONS = (1, 2, 3, 4, 4.1, 4.2, 4.3, 4.4, 4.5)
WEBHOOK_VERSIONS = (1, 1.1, 2, 2.1, 2.2)
BUNDLED_PREFIXES = ("n8n-nodes-base.", "@n8n/n8n-nodes-langchain.")
SENSITIVE_NAMES = {"authorization", "proxyauthorization", "cookie", "setcookie", "apikey", "xapikey",
                   "token", "accesstoken", "refreshtoken", "password", "passwd", "secret", "clientsecret"}
PLACEHOLDER = re.compile(r"(?i)(?:bearer\s+|basic\s+)?(?:<[^<>]+>|\*+|\[redacted\]|redacted|changeme|your[_ -]?(?:token|key|password))")
VARIABLE_EXPRESSION = re.compile(r"\s*=\s*\{\{\s*(?:\$env|\$vars|\$credentials|process\.env|_env|_vars)"
                                 r"(?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?P<q>['\"])[A-Za-z_][A-Za-z0-9_]*(?P=q)\])\s*\}\}\s*")


def _sensitive(name) -> bool:
    return isinstance(name, str) and re.sub(r"[-_ ]", "", name).lower() in SENSITIVE_NAMES


def _candidates(value, location, counter, limit):
    """Walk dictionaries with ordinal evidence; never include arbitrary keys."""
    counter[0] += 1
    if counter[0] > limit:
        raise InputError("ANALYSIS_VALUE_LIMIT", "Parameter traversal exceeds the analysis value limit")
    if isinstance(value, dict):
        pair = _sensitive(value.get("name")) and "value" in value
        for index, (key, item) in enumerate(value.items()):
            loc = f"{location}{{member:{index}}}"
            if _sensitive(key) or (pair and key == "value"):
                yield item, loc
            yield from _candidates(item, loc, counter, limit)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _candidates(item, f"{location}[{index}]", counter, limit)


def diagnose_nodes(data: dict, workflow_id: str, source: str, limits: AnalysisLimits | None = None) -> list[RiskFinding]:
    """Requires structurally validated input, like the dependency extractor."""
    limits = limits or AnalysisLimits()
    checks = []
    counter = [0]

    def add(rule, node, loc, message, suggestion, *, unknown=False, confidence="medium"):
        if len(checks) >= limits.max_dependencies:
            raise InputError("ANALYSIS_DIAGNOSTIC_LIMIT", "Node checks exceed the diagnostic limit")
        checks.append(RiskFinding(rule, "warning", "Unknown" if unknown else "Requires Review", workflow_id,
                                  fingerprint("node", node["id"]), loc, message, suggestion, confidence, source,
                                  assessment="unknown" if unknown else "risk"))

    for index, node in enumerate(data["nodes"]):
        base = f"$.nodes[{index}]"
        if not node["type"].startswith(BUNDLED_PREFIXES):
            add("WF015", node, base + ".type", "Node package availability is unknown on the destination",
                "Identify the package and version locally; review trust, licensing and destination installation policy. Do not install from this report.", unknown=True)
        if node["type"] == "n8n-nodes-base.webhook":
            unknown = node["typeVersion"] not in WEBHOOK_VERSIONS or is_expression(node["parameters"].get("path"))
            add("WF014", node, base + ".parameters.path", "Webhook endpoint and publication require migration review",
                "Review test versus production URLs, destination host, path, authentication, publication and upstream subscriptions manually.", unknown=unknown)
        if node["type"] != "n8n-nodes-base.httpRequest":
            continue
        known = node["typeVersion"] in HTTP_VERSIONS
        for value, loc in _candidates(node["parameters"], base + ".parameters", counter, limits.max_parameter_values):
            if value is None or value == "" or (isinstance(value, str) and not value.strip()):
                continue
            if isinstance(value, str) and (PLACEHOLDER.fullmatch(value.strip()) or VARIABLE_EXPRESSION.fullmatch(value)):
                continue
            unknown = not known or not isinstance(value, (str, int, float)) or isinstance(value, bool) or is_expression(value)
            add("WF011", node, loc,
                "Sensitive HTTP configuration cannot be resolved statically" if unknown else "Suspected hardcoded sensitive HTTP value; authenticity is unverified",
                "Inspect the value locally; prefer an n8n Credential or approved secret reference. Remove exposed literals before sharing; rotate only if a real secret was exposed.",
                unknown=unknown, confidence="low" if unknown else "medium")
        # JSON/header strings are intentionally not parsed or evaluated as code.
        for key in ("jsonHeaders", "headerParametersJson", "bodyParametersJson", "jsonBody"):
            value = node["parameters"].get(key)
            if isinstance(value, str) and value.strip() and not VARIABLE_EXPRESSION.fullmatch(value):
                add("WF011", node, base + ".parameters." + key,
                    "Serialized HTTP configuration requires local sensitive-value review",
                    "Review serialized configuration locally; this checker does not evaluate expressions or validate embedded secrets.", unknown=True, confidence="low")
    return checks


def environment_check(workflow_id: str, source: str) -> RiskFinding:
    return RiskFinding("WF016", "info", "Unknown", workflow_id, None, "$",
                       "Destination environment was not supplied; compatibility is unknown",
                       "Verify n8n and node versions, permissions, configuration and resources on an authorized destination before migration.",
                       "high", source, assessment="unknown")
