from pathlib import Path

from core import parsers


def test_markdown_file_is_supported_as_notes(tmp_path):
    path = tmp_path / "idea.md"
    path.write_text("# Idea\n\nThis is a reusable research note.", encoding="utf-8")

    assert parsers.detect_input_type(str(path)) == "notes"
    assert "reusable research note" in parsers.parse_text(str(path))


def test_srt_and_vtt_are_supported_as_transcripts(tmp_path):
    for suffix in (".srt", ".vtt"):
        path = tmp_path / f"lecture{suffix}"
        path.write_text("00:01\nSpeaker: causal inference lecture", encoding="utf-8")

        assert parsers.detect_input_type(str(path)) == "transcript"
        text, meta = parsers.parse_transcript(str(path))
        assert "causal inference lecture" in text
        assert meta["word_count"] > 0


def test_tsv_dataset_is_supported(tmp_path):
    path = tmp_path / "panel.tsv"
    path.write_text("id\tyear\ttreated\ty\n1\t2020\t0\t2.0\n1\t2021\t1\t3.0\n", encoding="utf-8")

    assert parsers.detect_input_type(str(path)) == "dataset"
    text, meta = parsers.parse_dataset(str(path))

    assert "Shape: 2 rows" in text
    assert meta["n_cols"] == 4


def test_audio_file_is_detected_but_requires_transcription(tmp_path):
    path = tmp_path / "seminar.mp3"
    path.write_bytes(b"not a real mp3")

    assert parsers.detect_input_type(str(path)) == "audio"
    text, meta = parsers.parse_audio(str(path))

    assert "Audio transcription required" in text
    assert meta["requires_transcription"] is True
