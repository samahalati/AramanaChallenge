"""Output guardrails. Six checks; the first four are deterministic and list-free, the last two are judged by an LLM (`judge.py`, rubric prompt):

  schema        shape, lengths, 1–5 findings, ≥2 verification steps
  citations     every cited ID exists; every finding cites ≥1 source
  numbers       every number in the text appears in the evidence (no invented statistics)
  identity      no e-mail, client reference or (known) person name; [judge] also disguised forms ("jane [at] x [dot] org")
  tone          [judge] no sanctions / accusations / conclusions of fraud
  consistency   [judge] the risk level is never softened or inflated

The model never scores, decides, or changes state: these checks only decide whether its WORDING may be shown.
"""
from __future__ import annotations

import json
import re

from detection.assistant.pack import EMAIL, Pack, fold

CHECKS = ["schema", "citations", "numbers", "identity", "tone", "consistency"]
JUDGED = ("tone", "consistency", "identity")
CITE = re.compile(r"\b[FIEBA]\d+\b")
NUM = re.compile(r"\d+(?:\.\d+)?")
CLIENT_REF = re.compile(r"\bC-\d{3,}\b")


def norm(x: str) -> str:
    f = float(x)
    return str(int(f)) if f == int(f) else f"{f:.4f}".rstrip("0").rstrip(".")


def allowed_numbers(pack: Pack) -> set[str]:
    out: set[str] = set()
    for text in pack.items.values():
        for n in NUM.findall(CITE.sub(" ", text)):
            f = float(n)
            out |= {norm(n), str(round(f)), f"{f:.1f}".rstrip("0").rstrip("."), norm(str(f * 100)) if f <= 1 else norm(n)}
    return out | {"1", "2", "3"}   # counting words ("two steps") are harmless


def parse_json(raw: str) -> dict | None:
    s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    for candidate in (s, s[s.find("{"): s.rfind("}") + 1] if "{" in s else ""):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except ValueError:
            continue
    return None


def strings(x):
    """All text a reply would show (citation lists excluded)."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k != "cites":
                yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def reply_text(data: dict) -> str:
    return fold("\n".join(strings(data)))   # Persian digits -> Latin, zero-width characters removed


def _cites(data: dict) -> list[str]:
    findings = data.get("findings") if isinstance(data.get("findings"), list) else []
    return [c for c in data.get("cites", []) + [c for f in findings if isinstance(f, dict) for c in f.get("cites", [])] if isinstance(c, str)]


def _schema(kind: str, d: dict) -> list[str]:
    ok_str = lambda x, n: isinstance(x, str) and 0 < len(x) <= n                                   # noqa: E731
    ok_list = lambda x, lo, hi, n: isinstance(x, list) and lo <= len(x) <= hi and all(ok_str(i, n) for i in x)   # noqa: E731
    if kind == "briefing":
        findings = d.get("findings")
        rules = [(ok_str(d.get("summary"), 600), "summary must be a non-empty string of at most 600 characters"),
                 (isinstance(findings, list) and 1 <= len(findings) <= 5 and all(isinstance(f, dict) and ok_str(f.get("text"), 300) and isinstance(f.get("cites"), list) for f in findings),
                  "findings must be 1-5 objects {text (<=300 chars), cites[]}"),
                 (ok_list(d.get("benign_explanations"), 1, 4, 250), "benign_explanations must be 1-4 short strings"),
                 (ok_list(d.get("verification_steps"), 2, 4, 250), "verification_steps must be 2-4 short strings")]
    else:
        rules = [(ok_str(d.get("answer"), 700), "answer must be a non-empty string of at most 700 characters"), (isinstance(d.get("cites"), list), "cites must be a list"),
                 (isinstance(d.get("insufficient_evidence"), bool), "insufficient_evidence must be true or false")]
    return [msg for ok, msg in rules if not ok]


def validate(kind: str, raw: str, pack: Pack, forbidden: set[str] = frozenset()) -> tuple[dict | None, dict[str, list[str]]]:
    """Deterministic checks. Returns (parsed or None, {check: [violations]}); the judged checks stay empty here (see judge.py)."""
    res: dict[str, list[str]] = {c: [] for c in CHECKS}
    data = parse_json(raw)
    if data is None:
        res["schema"].append("reply is not a single JSON object")
        return None, res
    res["schema"] += _schema(kind, data)
    cites = _cites(data)
    res["citations"] += [f"unknown source {c}" for c in dict.fromkeys(cites) if c not in pack.items]
    if kind == "briefing":
        res["citations"] += [f"finding without a source: “{f.get('text', '')[:50]}”" for f in data.get("findings", []) if isinstance(f, dict) and not f.get("cites")]
    elif not data.get("insufficient_evidence") and not data.get("refused") and not cites:
        res["citations"].append("answer has no cited source (use insufficient_evidence=true if the evidence cannot answer)")
    text, known = reply_text(data), fold(pack.render()).lower()
    allowed = allowed_numbers(pack)
    res["numbers"] += [f"number {n} does not appear in the evidence" for n in dict.fromkeys(norm(x) for x in NUM.findall(CITE.sub(" ", text))) if n not in allowed]
    res["identity"] += (["contains an e-mail address"] if EMAIL.search(text) else []) + (["contains a client reference"] if CLIENT_REF.search(text) else [])
    # a "name" that already occurs in the (pseudonymised) pack is an ordinary word such as a role title, not a leak
    res["identity"] += [f"contains a name ({n})" for n in forbidden if n and fold(n).lower() not in known and len(fold(n)) > 3 and fold(n).lower() in text.lower()]
    return data, res


def violations(res: dict[str, list[str]]) -> list[str]:
    return [f"{check}: {msg}" for check, msgs in res.items() for msg in msgs]
