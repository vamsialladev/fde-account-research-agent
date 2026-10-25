"""Stand-ins for the Anthropic client and the web: queued replies, cited text blocks, a fake page opener."""

import json
from contextlib import contextmanager
from types import SimpleNamespace


def usage(searches=0):
    return SimpleNamespace(
        input_tokens=1000, output_tokens=100, server_tool_use=SimpleNamespace(web_search_requests=searches)
    )


def cite(url, quote="", title="A page"):
    return SimpleNamespace(url=url, title=title, cited_text=quote)


def text(t, citations=None):
    return SimpleNamespace(type="text", text=t, citations=citations)


DEFAULT_PLAN = {
    "questions": [
        {"topic": "overview", "text": "Who are they?"},
        {"topic": "recent_news", "text": "What happened lately?"},
    ]
}


class FakeClient:
    """create(): plan JSON, research blocks or writer JSON, chosen by what's asked. stream(): a chat answer."""

    def __init__(
        self, research_blocks=None, writer=None, plan=None, answer="It has 1,528 properties [F1].", rewrite=""
    ):
        self.research_blocks, self.writer, self.plan = research_blocks, writer, plan
        self.answer, self.rewrite, self.requests = answer, rewrite, []
        self.messages = self

    def create(self, **req):
        self.requests.append(req)
        if req.get("tools"):
            blocks = self.research_blocks(req) if callable(self.research_blocks) else self.research_blocks
            return SimpleNamespace(content=blocks, usage=usage(searches=2))
        fmt = req.get("output_config", {}).get("format")
        if fmt and "questions" in fmt["schema"]["properties"]:
            return SimpleNamespace(content=[text(json.dumps(self.plan or DEFAULT_PLAN))], usage=usage())
        if fmt:
            return SimpleNamespace(content=[text(json.dumps(self.writer))], usage=usage())
        return SimpleNamespace(content=[text(self.rewrite)], usage=usage())

    @contextmanager
    def stream(self, **req):
        self.requests.append(req)
        final = SimpleNamespace(usage=usage())
        yield SimpleNamespace(text_stream=iter([self.answer]), get_final_message=lambda: final)


WRITER = {
    "snapshot": [
        {"text": "It runs 1,528 properties.", "findings": ["F1"]},
        {"text": "Uncited line.", "findings": ["F99"]},
    ],
    "recent_news": [],
    "guest_themes": [],
    "tech_hints": [],
    "discovery_questions": [f"Question {i}?" for i in range(1, 11)],
    "use_cases": [
        {
            "name": "Front-desk assistant",
            "why": "Slow check-in.",
            "findings": ["F1"],
            "felt": "probably",
            "would_pay": "unknown",
            "buildable_in_a_week": "yes",
            "first_user_known": "unknown",
        }
    ],
    "email": "Hi,\n\nWould a 30-minute call next week work?\n\nVamsi",
}


class FakeWeb:
    """A page opener: {url: html}. Anything else is unreachable."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise OSError("unreachable")
        return self.pages[url].encode()
