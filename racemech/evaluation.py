"""Score answers against eval/questions.yaml and compare models."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from racemech.config import REPO_ROOT

QUESTIONS = REPO_ROOT / "eval" / "questions.yaml"
_DECLINE = re.compile(
    r"don'?t have|do not have|no information|not (?:available|in the|enough information|known|released)|"
    r"can'?t (?:answer|tell|say|predict|help)|cannot (?:answer|tell|say|predict|help)|unable to|"
    r"no data|isn'?t (?:in|available|known)|not something i|doesn'?t (?:contain|include|exist|mention)|"
    r"does not (?:contain|include|exist|mention)|unknown|not sure|"
    r"no (?:relevant )?information (?:was )?found|impossible to (?:determine|say|know|predict)", re.I)
_NUM = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])-?\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Score:
    id: str
    category: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    unsupported_numbers: list[float] = field(default_factory=list)
    seconds: float = 0.0
    answer: str = ""


def unsupported(answer: str, context: str, question: str) -> list[float]:
    """Numbers in the answer that appear in neither the context nor the question (rounding allowed)."""
    known = numbers_in(context) + numbers_in(question)
    bad = []
    for n in numbers_in(answer):
        if abs(n) <= 10 and float(n).is_integer():
            continue                                  # small counts ("2 debuffers", "3 skills") are fine
        if not any(abs(n - k) <= max(0.5, abs(k) * 0.01) or abs(n - k * 100) < 0.05 or abs(n * 100 - k) < 0.05
                   for k in known):
            bad.append(n)
    return bad


def score(q: dict, answer: str, context: str) -> Score:
    s = Score(q["id"], q.get("category", ""), True, answer=answer)
    low = answer.lower()
    nums = numbers_in(answer)
    for spec in q.get("numbers", []):
        if not any(abs(n - spec["value"]) <= spec.get("tol", 0) for n in nums):
            s.failures.append(f"missing number {spec['value']}±{spec.get('tol', 0)}")
    for group in q.get("keywords", []):
        if not any(alt.lower() in low for alt in group):
            s.failures.append(f"missing one of {group}")
    for bad in q.get("forbid", []):
        if bad.lower() in low:
            s.failures.append(f"contains forbidden {bad!r}")
    if q.get("decline") and not _DECLINE.search(answer):
        s.failures.append("should have declined")
    s.unsupported_numbers = [] if q.get("decline") else unsupported(answer, context, q["question"])
    s.passed = not s.failures
    return s


def run(assistant, questions: list[dict], only: set[str] | None = None, echo=print) -> list[Score]:
    scores = []
    for q in questions:
        if only and q["id"] not in only:
            continue
        t0 = time.perf_counter()
        ans = assistant.ask(q["question"])
        sc = score(q, ans.reply.text, ans.context.render())
        sc.seconds = time.perf_counter() - t0
        scores.append(sc)
        flag = "PASS" if sc.passed else "FAIL"
        extra = f"  invented: {sc.unsupported_numbers}" if sc.unsupported_numbers else ""
        echo(f"{flag}  {sc.id:42} {sc.seconds:5.1f}s  {'; '.join(sc.failures)}{extra}")
    return scores


def summary(model: str, scores: list[Score]) -> dict:
    by_cat: dict[str, list[Score]] = {}
    for s in scores:
        by_cat.setdefault(s.category, []).append(s)
    return {
        "model": model,
        "passed": sum(s.passed for s in scores),
        "total": len(scores),
        "with_invented_numbers": sum(bool(s.unsupported_numbers) for s in scores),
        "median_seconds": sorted(s.seconds for s in scores)[len(scores) // 2] if scores else 0,
        "by_category": {c: f"{sum(x.passed for x in v)}/{len(v)}" for c, v in sorted(by_cat.items())},
    }


def write_report(model: str, scores: list[Score], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    path = out_dir / f"eval-{safe}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps({"summary": summary(model, scores), "results": [asdict(s) for s in scores]},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return path
