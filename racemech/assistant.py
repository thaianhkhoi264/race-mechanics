"""The full pipeline: question -> context (code) -> one model call -> answer."""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from importlib import resources

from racemech.botlib import BotLib
from racemech.config import Settings
from racemech.context import Context, ContextBuilder
from racemech.evaluation import numbers_in
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
    voice_path: str = ""          # "rewritten" | "fallback" when a voice is on


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
        self.voice_system = voice_prompt(self.voice)
        self.character_names = {c.name for c in self.botlib.game.cards.values()}
        self.system = system_prompt() + self.reference

    def ask(self, question: str) -> Answer:
        ctx = self.builder.build(question)
        user = f"CONTEXT\n\n{ctx.render()}\n\nQUESTION\n{question}"
        reply = self.client.chat(self.system, user)
        answer = Answer(question, ctx, reply)
        if self.voice:
            self._apply_voice(answer)
        return answer

    def _apply_voice(self, answer: Answer) -> None:
        """Second pass: rewrite the plain answer in the voice. The rewrite is kept only if it has
        exactly the plain answer's numbers; otherwise the plain answer gets a short in-voice opener."""
        plain = answer.reply.text
        pool = BAD_NEWS_OPENERS if _BAD_NEWS.search(plain) else OPENERS
        opener = pool[zlib.crc32(answer.question.encode("utf-8")) % len(pool)]
        voiced = self.client.chat(self.voice_system, f"OPENING: {opener}\n\nANSWER\n\n{plain}")
        answer.reply.seconds += voiced.seconds
        answer.reply.output_tokens += voiced.output_tokens
        candidate = tidy_voice(voiced.text)
        same_numbers = sorted(numbers_in(candidate)) == sorted(numbers_in(plain))
        new_names = {n for n in self.character_names if n in candidate and n not in plain}
        if voiced.text and same_numbers and not new_names:
            answer.reply.text, answer.voice_path = candidate, "rewritten"
        else:
            answer.reply.text, answer.voice_path = f"{opener} {plain}", "fallback"
