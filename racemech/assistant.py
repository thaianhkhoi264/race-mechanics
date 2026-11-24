"""The full pipeline: question -> context (code) -> one model call -> answer."""
from __future__ import annotations

import re
import tomllib
import zlib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from racemech.botlib import BotLib
from racemech.config import Settings
from racemech.context import Context, ContextBuilder
from racemech.evaluation import numbers_in, unsupported
from racemech.llm import OllamaClient, Reply
from racemech.retrieval import build_index


def system_prompt() -> str:
    return resources.files("racemech").joinpath("prompts/system.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Persona:
    """An answer voice, loaded from a TOML file (see docs/persona.example.toml). The prompt is
    appended to the system prompt; the other fields are enforced in code."""
    prompt: str = ""
    openers: tuple[str, ...] = ()            # one is prefixed when the answer doesn't open in voice
    bad_news_openers: tuple[str, ...] = ()   # used instead when the verdict is negative
    in_voice: str = ""                       # regex: the opening already sounds in voice
    note: str = ""                           # decoration kept at most once, never on bad news


def load_persona(path: str | Path | None) -> Persona | None:
    """None for plain answers (empty setting); otherwise the persona in that TOML file."""
    if not path or not str(path).strip():
        return None
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"persona file not found: {p}")
    with p.open("rb") as f:
        raw = tomllib.load(f)
    return Persona(prompt=raw.get("prompt", ""), openers=tuple(raw.get("openers", ())),
                   bad_news_openers=tuple(raw.get("bad_news_openers", ())),
                   in_voice=raw.get("in_voice", ""), note=raw.get("note", ""))


# Bad news, refusals and declines: no persona note on these (enforced in code).
_BAD_NEWS = re.compile(
    r"\b(not enough|short of|does not activate|doesn't activate|cannot activate|can't activate|"
    r"won't activate|does not fire|doesn't fire|I'm afraid|I don't have|I do not have|"
    r"don't have (?:that|any|information|data)|not available|unavailable|no information)\b", re.I)


_KEY_LINE = re.compile(r"^- ((?:VERDICT|RECOMMENDATION)[^\n]*)$", re.M)
_NEGATIVE = re.compile(r"does NOT have enough|short of|not enough|CANNOT ACTIVATE|USELESS", re.I)


def required_numbers(context: str) -> list[float]:
    """Numbers the answer must keep: everything on VERDICT / RECOMMENDATION lines (the facts the
    voice used to drop), excluding small counts."""
    out = []
    for line in _KEY_LINE.findall(context):
        out += [n for n in numbers_in(line) if not (abs(n) <= 10 and float(n).is_integer())]
    return out


def voice_problems(text: str, context: str, question: str, character_names: set[str]) -> list[str]:
    """Why a voiced answer can't be used as-is (empty list = fine)."""
    problems = []
    if not text.strip():
        return ["empty answer"]
    invented = unsupported(text, context, question)
    if invented:
        problems.append(f"numbers not in the context: {invented}")
    have = numbers_in(text)
    missing = [n for n in required_numbers(context)
               if not any(abs(n - h) <= max(0.5, abs(n) * 0.01) for h in have)]
    if missing:
        problems.append(f"dropped key numbers: {missing}")
    names = {n for n in character_names if n in text and n not in context and n not in question}
    if names:
        problems.append(f"named characters not in the question: {sorted(names)}")
    return problems


def _opener(question: str, context: str, persona: Persona) -> str:
    """A persona opener picked per question, so answers don't all start the same way ("" if none)."""
    pool = persona.bad_news_openers if _NEGATIVE.search(context) else persona.openers
    return pool[zlib.crc32(question.encode("utf-8")) % len(pool)] if pool else ""


def _in_voice(text: str, persona: Persona) -> bool:
    """The opening already sounds like the persona (otherwise code adds an opener)."""
    return bool(persona.in_voice) and re.search(persona.in_voice, text[:160], re.M) is not None


def _with_opener(opener: str, text: str) -> str:
    return f"{opener} {text}" if opener else text


def tidy_voice(text: str, note: str) -> str:
    """No note on bad news or declines; at most one note otherwise."""
    if not note or note not in text:
        return text
    strip = re.compile(" ?" + re.escape(note))
    if _BAD_NEWS.search(text):
        return strip.sub("", text)
    first = text.index(note) + len(note)
    return text[:first] + strip.sub("", text[first:])


def mechanics_reference() -> str:
    doc = resources.files("racemech").joinpath("knowledge/mechanics.md").read_text(encoding="utf-8")
    return ("\n\nRACE MECHANICS REFERENCE (part of the CONTEXT for every question; quote its numbers "
            "as written)\n\n" + doc)


@dataclass
class Answer:
    question: str
    context: Context
    reply: Reply
    voice_path: str = ""          # "voiced" | "fallback: <why>" when a voice is on


class Assistant:
    def __init__(self, settings: Settings, model: str | None = None, voice: str | None = None):
        self.settings = settings
        self.botlib = BotLib(settings.bot_repo, settings.data_dir, settings.sim_module).load()
        exclude = frozenset({"mechanics"}) if settings.full_mechanics else frozenset()
        index = build_index(settings.bot_repo, exclude)
        self.builder = ContextBuilder(self.botlib, index, settings.retrieval_k)
        self.client = OllamaClient(settings.ollama_url, model or settings.model, settings.timeout_s,
                                   settings.keep_alive, settings.temperature, settings.num_ctx)
        self.reference = mechanics_reference() if settings.full_mechanics else ""
        self.persona = load_persona(settings.voice if voice is None else voice)
        self.voice = self.persona is not None
        self.character_names = {c.name for c in self.botlib.game.cards.values()}
        self.system = system_prompt() + self.reference
        # The voice goes last: it stays salient after the long reference, and the prefix matches the
        # plain prompt so Ollama's prompt cache serves both.
        self.voice_system = self.system + (self.persona.prompt if self.persona else "")

    def ask(self, question: str) -> Answer:
        ctx = self.builder.build(question)
        user = f"CONTEXT\n\n{ctx.render()}\n\nQUESTION\n{question}"
        if not self.voice:
            return Answer(question, ctx, self.client.chat(self.system, user))
        # Answer in the voice in one pass; keep it only if code checks pass, else answer plainly.
        reply = self.client.chat(self.voice_system, user)
        persona = self.persona
        text = tidy_voice(reply.text, persona.note)
        problems = voice_problems(text, ctx.render() + self.reference, question, self.character_names)
        if not problems:
            if not _in_voice(text, persona):
                text = _with_opener(_opener(question, ctx.render(), persona), text)  # at least an opener
            reply.text = text
            return Answer(question, ctx, reply, "voiced")
        plain = self.client.chat(self.system, user)
        plain.seconds += reply.seconds
        plain.output_tokens += reply.output_tokens
        plain.text = _with_opener(_opener(question, ctx.render(), persona), plain.text)
        return Answer(question, ctx, plain, "fallback: " + "; ".join(problems))
