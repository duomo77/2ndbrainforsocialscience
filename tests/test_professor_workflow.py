from pathlib import Path

from ui.workflow import InputDraft, validate_input_draft


def test_paper_requires_title_and_content_or_file():
    result = validate_input_draft(InputDraft(input_type="paper"))

    assert result.ready is False
    assert result.field == "title"
    assert "논문 제목" in result.message


def test_paper_with_title_and_file_is_ready():
    result = validate_input_draft(
        InputDraft(input_type="paper", title="Causal Inference", file_path="paper.pdf")
    )

    assert result.ready is True
    assert result.message == "분석 준비 완료"


def test_dataset_requires_name_but_accepts_description():
    missing = validate_input_draft(InputDraft(input_type="dataset", raw_text="panel data description"))
    ready = validate_input_draft(
        InputDraft(input_type="dataset", title="Korean Labor Panel", raw_text="panel data description")
    )

    assert missing.ready is False
    assert missing.field == "title"
    assert ready.ready is True


def test_equation_does_not_require_title():
    result = validate_input_draft(InputDraft(input_type="equation", raw_text="E[Y(1)-Y(0)]"))

    assert result.ready is True


def test_main_window_professor_defaults_and_recent_paths(qt_app, monkeypatch, tmp_path):
    from ui import main_window

    monkeypatch.setattr(main_window.MainWindow, "_open_settings", lambda self: None)
    monkeypatch.setattr(main_window.memory, "load_recent_sessions", lambda n=10: [
        {
            "type": "paper",
            "title": "Minimum Wage Study",
            "path": str(tmp_path / "Minimum Wage Study.md"),
        }
    ])

    window = main_window.MainWindow()

    assert window.t_date.text()
    assert window.readiness_label.text()
    item = window.recent_list.topLevelItem(0)
    assert item.data(0, main_window.Qt.ItemDataRole.UserRole) == str(tmp_path / "Minimum Wage Study.md")


def test_text_paper_file_uses_filename_as_title(qt_app, monkeypatch, tmp_path):
    from ui import main_window

    paper = tmp_path / "Difference in Differences.md"
    paper.write_text("# Paper", encoding="utf-8")
    monkeypatch.setattr(main_window.MainWindow, "_open_settings", lambda self: None)
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(paper), ""),
    )

    window = main_window.MainWindow()
    window._pick_file("paper")

    assert window.p_title.text() == "Difference in Differences"
