import types

from core import ros_engine


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(model=kwargs["model"])


class _FakeClient:
    def __init__(self):
        self.completions = _FakeCompletions()
        self.chat = types.SimpleNamespace(completions=self.completions)


def test_validate_api_uses_non_streaming_probe(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(ros_engine, "_build_client", lambda api_key, base_url: fake_client)

    ok, message = ros_engine.validate_api("test-key", "", "gpt-test")

    assert ok is True
    assert "OPENAI" in message
    assert fake_client.completions.calls == [
        {
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0,
            "max_tokens": 5,
            "stream": False,
        }
    ]


def test_validate_api_rejects_missing_required_fields_without_network(monkeypatch):
    monkeypatch.setattr(
        ros_engine,
        "_build_client",
        lambda api_key, base_url: (_ for _ in ()).throw(AssertionError("network should not be touched")),
    )

    ok, message = ros_engine.validate_api("", "", "gpt-test")

    assert ok is False
    assert "API key" in message


def test_china_provider_base_urls_are_detected():
    cases = {
        "https://api.deepseek.com": "deepseek",
        "https://dashscope.aliyuncs.com/compatible-mode/v1": "qwen",
        "https://open.bigmodel.cn/api/paas/v4": "zhipu",
        "https://api.moonshot.ai/v1": "moonshot",
        "https://api.minimax.chat/v1": "minimax",
        "https://qianfan.baidubce.com/v2": "baidu",
        "https://api.siliconflow.cn/v1": "siliconflow",
        "https://api.lingyiwanwu.com/v1": "01ai",
    }

    for base_url, provider in cases.items():
        assert ros_engine._detect_provider(base_url, "custom-model") == provider


def test_qwen3_validation_disables_thinking(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(ros_engine, "_build_client", lambda api_key, base_url: fake_client)

    ok, message = ros_engine.validate_api(
        "test-key",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen3-72b",
    )

    assert ok is True
    assert "QWEN" in message
    assert fake_client.completions.calls[0]["extra_body"] == {"enable_thinking": False}


def test_extract_graph_edges_is_deterministic_and_dedupes_links():
    markdown = """---
title: Test
tags: [causal-inference, DML]
---

# [[Double Machine Learning]]

This note links [[DML]] and [[Causal Forest|forest]].
It repeats [[DML]] and mentions #econometrics.
"""

    edges = ros_engine.extract_graph_edges("", "", "gpt-test", markdown)

    assert edges["explicit_links"] == ["Double Machine Learning", "DML", "Causal Forest"]
    assert edges["tags"] == ["causal-inference", "DML", "econometrics"]
    assert set(edges["implicit_links"]) >= {"causal-inference", "econometrics"}
