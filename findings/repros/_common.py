"""Shared helpers for building viewer-bug repro .eval files.

Import from task files as::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[2]))  # findings/repros/
    from _common import bug_description, bug_sample, mock_text, mock_tool_call

All helpers here are thin wrappers over public ``inspect_ai`` APIs so that
repro task files stay short and consistent. Everything runs against
``mockllm/model`` — no real model APIs are ever called.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any

from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.model import (
    ChatMessageAssistant,
    ModelOutput,
)
from inspect_ai.tool import ToolCall

# 1x1 transparent PNG (67 bytes) — handy for ContentImage repros without
# shipping a real image file.
TINY_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


# ---------------------------------------------------------------------------
# Bug-description formatting
# ---------------------------------------------------------------------------


def bug_description(
    finding_id: str,
    title: str,
    observed: str,
    expected: str,
    where_to_look: str,
    extra: str | None = None,
) -> str:
    """Format a standard human-readable bug description block.

    Embed the returned string as the ``Sample.input`` (or first user message)
    so that anyone opening the log in ``inspect view`` immediately sees what
    bug this file demonstrates and where to look for it.

    Args:
        finding_id: e.g. ``"F01.3"`` — must match the findings/*.md ID.
        title: One-line summary of the bug.
        observed: What the viewer currently (incorrectly) shows.
        expected: What the viewer *should* show.
        where_to_look: UI navigation hint, e.g.
            ``"Sample → Transcript tab → expand the 'Score Edit' event"``.
        extra: Optional free-form additional notes (markdown).

    Returns:
        A markdown string. The viewer renders sample input / user messages as
        markdown so headings and bold work.
    """
    body = dedent(f"""\
        # VIEWER BUG REPRO — {finding_id}

        **{title}**

        | | |
        |---|---|
        | **Where to look** | {where_to_look} |
        | **Observed (bug)** | {observed} |
        | **Expected** | {expected} |
        | **Finding file** | `findings/{finding_id.split(".")[0][1:].zfill(2)}-*.md` |
        """)
    if extra:
        body += "\n" + dedent(extra).strip() + "\n"
    return body


def emit_bug_banner(desc: str) -> None:
    """Emit the bug description as an InfoEvent so it's the first visible thing in the Transcript tab.

    ``Sample.input`` is truncated in the sample-dialog header and the
    ``SampleInit`` event that carries it is filtered out of the transcript by
    default, so a user opening a repro can't easily see what to look for.
    Emitting the description as an ``InfoEvent`` fixes that: ``info`` is not in
    the default exclude list, ``InfoEventView`` renders string data as
    markdown, and the panel is expanded by default.

    Call this as the **first line** of every repro solver's ``solve()`` body.
    """
    transcript().info(desc, source="bug-repro")


def bug_sample(
    finding_id: str,
    title: str,
    observed: str,
    expected: str,
    where_to_look: str,
    *,
    target: str | list[str] = "n/a",
    metadata: dict[str, Any] | None = None,
    extra: str | None = None,
    sample_id: str | int | None = None,
) -> Sample:
    """Build a ``Sample`` whose input is a :func:`bug_description` block.

    This is the easiest way to start a repro: the description is the user
    prompt, so it is the first thing visible in both the Messages tab and the
    Transcript tab. For repros that need a *specific* input shape (e.g. a
    list of ChatMessages, or an image), build the ``Sample`` by hand and put
    the description in ``Sample.metadata["bug"]`` and/or a system message.
    """
    md = {"finding_id": finding_id, "bug_title": title}
    if metadata:
        md.update(metadata)
    return Sample(
        id=sample_id or finding_id,
        input=bug_description(finding_id, title, observed, expected, where_to_look, extra),
        target=target,
        metadata=md,
    )


# ---------------------------------------------------------------------------
# mockllm output helpers
# ---------------------------------------------------------------------------


def mock_text(text: str, *, stop_reason: str = "stop") -> ModelOutput:
    """A plain-text assistant completion from mockllm."""
    return ModelOutput.from_content(model="mockllm/model", content=text, stop_reason=stop_reason)  # type: ignore[arg-type]


def mock_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    content: str | None = None,
    tool_call_id: str | None = None,
) -> ModelOutput:
    """An assistant turn that calls a single tool."""
    return ModelOutput.for_tool_call(
        model="mockllm/model",
        tool_name=tool_name,
        tool_arguments=arguments,
        content=content,
        tool_call_id=tool_call_id,
    )


def mock_assistant(
    content: str | list[Any],
    *,
    tool_calls: list[ToolCall] | None = None,
    stop_reason: str = "stop",
) -> ModelOutput:
    """Full control over the assistant message (multi-content, multi-tool-call, etc.)."""
    msg = ChatMessageAssistant(
        content=content,
        model="mockllm/model",
        source="generate",
        tool_calls=tool_calls,
    )
    return ModelOutput.from_message(msg, stop_reason=stop_reason)  # type: ignore[arg-type]


__all__ = [
    "TINY_PNG_DATA_URI",
    "bug_description",
    "bug_sample",
    "emit_bug_banner",
    "mock_text",
    "mock_tool_call",
    "mock_assistant",
]
