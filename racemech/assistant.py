"""The full pipeline: question -> context (code) -> one model call -> answer."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from racemech.botlib import BotLib
from racemech.config import Settings
from racemech.context import Context, ContextBuilder
from racemech.llm import OllamaClient, Reply
from racemech.retrieval import build_index


def system_prompt() -> str:
    return resources.files("racemech").joinpath("prompts/system.md").read_text(encoding="utf-8")


def mechanics_reference() -> str:
    doc = resources.files("racemech").joinpath("knowledge/mechanics.md").read_text(encoding="utf-8")
    return ("\n\nRACE MECHANICS REFERENCE (part of the CONTEXT for every question; quote its numbers "
            "as written)\n\n" + doc)


@dataclass
class Answer:
    question: str
    context: Context
    reply: Reply


class Assistant:
    def __init__(self, settings: Settings, model: str | None = None):
        self.settings = settings
        self.botlib = BotLib(settings.bot_repo, settings.data_dir).load()
        exclude = frozenset({"mechanics"}) if settings.full_mechanics else frozenset()
        index = build_index(settings.bot_repo, exclude)
        self.builder = ContextBuilder(self.botlib, index, settings.retrieval_k)
        self.client = OllamaClient(settings.ollama_url, model or settings.model, settings.timeout_s,
                                   settings.keep_alive, settings.temperature, settings.num_ctx)
        self.reference = mechanics_reference() if settings.full_mechanics else ""
        self.system = system_prompt() + self.reference

    def ask(self, question: str) -> Answer:
        ctx = self.builder.build(question)
        user = f"CONTEXT\n\n{ctx.render()}\n\nQUESTION\n{question}"
        return Answer(question, ctx, self.client.chat(self.system, user))
