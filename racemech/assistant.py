"""The full pipeline: question -> context (code) -> one model call -> answer."""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from importlib import resources

from racemech.botlib import BotLib
from racemech.config import Settings
from racemech.context import Context, ContextBuilder
from racemech.evaluation import numbers_in, unsupported
from racemech.llm import OllamaClient, Reply
from racemech.retrieval import build_index


def system_prompt() -> str:
    return resources.files("racemech").joinpath("prompts/system.md").read_text(encoding="utf-8")


VOICES = {"persona": "prompts/voice_persona.md"}


def voice_prompt(voice: str) -> str:
    if not voice:
        return ""
    if voice not in VOICES:
        raise ValueError(f"unknown voice {voice!r}; choose from: {', '.join(VOICES)}")
    return resources.files("racemech").joinpath(VOICES[voice]).read_text(encoding="utf-8")


# Bad news, refusals and declines: no ♪ on these (voice rule, enforced in code).
_BAD_NEWS = re.compile(
    r"\b(not enough|short of|does not activate|doesn't activate|cannot activate|can't activate|"
    r"won't activate|does not fire|doesn't fire|I'm afraid|I don't have|I do not have|"
    r"don't have (?:that|any|information|data)|not available|unavailable|no information)\b", re.I)


# Openers in the persona's style, picked per question so answers don't all start the same way.
OPENERS = ("Of course, Trainer!", "Ah, a good question!", "Leave it to me!",
           "Let's see what the numbers say!", "Happy to help, Trainer!", "Here's what I found!")
BAD_NEWS_OPENERS = ("Hm, I see...", "I'm afraid this one is bad news...", "Oh dear...",
                    "Let me be honest...")


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


# Signs the opening already sounds like her (otherwise code adds an opener).
_IN_VOICE = re.compile(r"Trainer|Hehe|♪|Oh dear|Oh no|I'm afraid|Let's|Shall we|Of course|Leave it to me|"
                       r"^(?:Ah|Hm|Oh|Wow|Bravo)\b|Happy to help|Let me", re.M)


def _opener(question: str, context: str) -> str:
    pool = BAD_NEWS_OPENERS if _NEGATIVE.search(context) else OPENERS
    return pool[zlib.crc32(question.encode("utf-8")) % len(pool)]


def tidy_voice(text: str) -> str:
    """No ♪ on bad news or declines; at most one ♪ otherwise."""
    if "♪" not in text:
        return text
    if _BAD_NEWS.search(text):
        return re.sub(r" ?♪", "", text)
    first = text.index("♪") + 1
    return text[:first] + re.sub(r" ?♪", "", text[first:])


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
        self.botlib = BotLib(settings.bot_repo, settings.data_dir).load()
        exclude = frozenset({"mechanics"}) if settings.full_mechanics else frozenset()
        index = build_index(settings.bot_repo, exclude)
        self.builder = ContextBuilder(self.botlib, index, settings.retrieval_k)
        self.client = OllamaClient(settings.ollama_url, model or settings.model, settings.timeout_s,
                                   settings.keep_alive, settings.temperature, settings.num_ctx)
        self.reference = mechanics_reference() if settings.full_mechanics else ""
        self.voice = settings.voice if voice is None else voice
        self.character_names = {c.name for c in self.botlib.game.cards.values()}
        self.system = system_prompt() + self.reference
        # The voice goes last: it stays salient after the long reference, and the prefix matches the
        # plain prompt so Ollama's prompt cache serves both.
        self.voice_system = self.system + voice_prompt(self.voice)

    def ask(self, question: str) -> Answer:
        ctx = self.builder.build(question)
        user = f"CONTEXT\n\n{ctx.render()}\n\nQUESTION\n{question}"
        if not self.voice:
            return Answer(question, ctx, self.client.chat(self.system, user))
        # Answer in the voice in one pass; keep it only if code checks pass, else answer plainly.
        reply = self.client.chat(self.voice_system, user)
        text = tidy_voice(reply.text)
        problems = voice_problems(text, ctx.render() + self.reference, question, self.character_names)
        if not problems:
            if not _IN_VOICE.search(text[:160]):
                text = f"{_opener(question, ctx.render())} {text}"      # always at least an opener
            reply.text = text
            return Answer(question, ctx, reply, "voiced")
        plain = self.client.chat(self.system, user)
        plain.seconds += reply.seconds
        plain.output_tokens += reply.output_tokens
        plain.text = f"{_opener(question, ctx.render())} {plain.text}"
        return Answer(question, ctx, plain, "fallback: " + "; ".join(problems))
