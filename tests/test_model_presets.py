from ui.settings_dialog import PRESET_MODELS, PRESET_MODELS_CHINA, PRESET_MODELS_GLOBAL


def test_global_presets_prefer_current_generation_models():
    assert PRESET_MODELS_GLOBAL[:3] == ["gpt-5.2", "gpt-5.2-pro", "gpt-5.1"]
    assert "gpt-4-turbo" not in PRESET_MODELS_GLOBAL
    assert "o3-mini" not in PRESET_MODELS_GLOBAL


def test_china_presets_drop_known_legacy_first_choices():
    assert PRESET_MODELS_CHINA["DeepSeek (深度求索)"] == [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ]
    assert "deepseek-chat" not in PRESET_MODELS_CHINA["DeepSeek (深度求索)"]
    assert "abab5.5-chat" not in PRESET_MODELS_CHINA["MiniMax (稀宇科技)"]
    assert "ernie-3.5-128k" not in PRESET_MODELS_CHINA["Baidu ERNIE (文心一言)"]


def test_presets_include_broader_modern_china_options():
    assert "qwen3-max" in PRESET_MODELS_CHINA["Qwen / 通义千问 (Alibaba)"]
    assert "kimi-k2.5" in PRESET_MODELS_CHINA["Moonshot Kimi (月之暗面)"]
    assert "MiniMax-M2.7" in PRESET_MODELS_CHINA["MiniMax (稀宇科技)"]
    assert "ernie-5.0" in PRESET_MODELS_CHINA["Baidu ERNIE (文心一言)"]
    assert "Qwen/Qwen3.6-35B-A3B" in PRESET_MODELS_CHINA["SiliconFlow (硅基流动)"]


def test_flat_model_list_contains_all_provider_presets():
    for model in PRESET_MODELS_GLOBAL:
        assert model in PRESET_MODELS
    for provider_models in PRESET_MODELS_CHINA.values():
        for model in provider_models:
            assert model in PRESET_MODELS
