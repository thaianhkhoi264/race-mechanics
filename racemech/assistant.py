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


@dataclass
class Answer:
    question: str
    context: Context
    reply: Reply


class Assistant:
    def __init__(self, settings: Settings, model: str | None = None):
        self.settings = settings
        self.botlib = BotLib(settings.bot_repo, settings.data_dir).load()
        self.builder = ContextBuilder(self.botlib, build_index(settings.bot_repo), settings.retrieval_k)
        self.client = OllamaClient(settings.ollama_url, model or settings.model, settings.timeout_s,
                                   settings.keep_alive, settings.temperature)
        self.system = system_prompt()

    def ask(self, question: str) -> Answer:
        ctx = self.builder.build(question)
        user = f"CONTEXT\n\n{ctx.render()}\n\nQUESTION\n{question}"
        return Answer(question, ctx, self.client.chat(self.system, user))
