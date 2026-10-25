"""The data that moves between the agents. Plain dataclasses, so every step can be shown, saved and tested."""

from dataclasses import dataclass, field

TOPICS = {
    "overview": "Company overview: what it is, size, ownership, headquarters, brands",
    "properties": "Properties: how many, where, which segments (resort, city, all-inclusive...)",
    "recent_news": "Recent news from the last 12 months: openings, deals, results, leadership changes",
    "guest_feedback": "Themes in public guest reviews (aggregated; never individual reviewers)",
    "technology": "Technology hints: booking engine, PMS, apps, loyalty platform, published tech partners",
    "ai_opportunities": "Where AI could help this company's operations, based on what's public",
}


@dataclass
class Question:
    id: str  # Q1..
    topic: str  # one of TOPICS
    text: str


@dataclass
class Source:
    url: str
    title: str = ""
    cited_text: str = ""
    verified: str = "not checked"  # found | not found | robots.txt | unreachable | not checked


@dataclass
class Finding:
    id: str  # F1..
    topic: str
    claim: str
    sources: list = field(default_factory=list)  # [Source]
    flags: list = field(default_factory=list)  # stale | personal data removed | ...


@dataclass
class Step:
    name: str
    input: dict
    result: dict
    seconds: float = 0.0
    cost_usd: float = 0.0


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    calls: int = 0

    def add(self, message) -> None:
        self.input_tokens += message.usage.input_tokens
        self.output_tokens += message.usage.output_tokens
        server = getattr(message.usage, "server_tool_use", None)
        self.searches += int(getattr(server, "web_search_requests", 0) or 0)
        self.calls += 1

    def cost(self, price_in: float, price_out: float, price_search_1k: float) -> float:
        return (
            self.input_tokens * price_in + self.output_tokens * price_out
        ) / 1e6 + self.searches * price_search_1k / 1000
