from __future__ import annotations

import asyncio
import json
import socket

import httpx

from app.ai.context.builder import ContextPackBuilder
from app.ai.translation.service import translate_blocks


class LocalTokenizerFixture:
    def encode(self, value, add_special_tokens=False):
        return list(range(max(1, len(str(value)) // 4)))

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=True):
        return self.encode(json.dumps(messages))


def run_private(ir):
    requests = []

    def response(request):
        payload = json.loads(request.content)
        document = json.loads(payload["messages"][1]["content"])
        requests.append(document)
        items = [
            {"id": block["id"], "text": "Traduction synthétique " + block["text"]}
            for block in document["blocks"]
        ]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps({"translations": items})},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    result = asyncio.run(
        translate_blocks(
            ir,
            {
                "engine": "private",
                "private_ai_base_url": "http://qwen-fixture.test/v1",
                "private_ai_allowed_hosts": ["qwen-fixture.test"],
                "private_ai_model": "private-fixture",
                "tokenizer": LocalTokenizerFixture(),
                "resolver": lambda *args, **kwargs: [
                    (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.2", 80))
                ],
                "transport": httpx.MockTransport(response),
            },
        )
    )
    return result, requests


def table_ir():
    return {
        "language": "eng",
        "domain": "BANKING",
        "document_type": "bank_statement",
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "b1",
                        "page": 1,
                        "text": "Account 123",
                        "language": "eng",
                        "bbox": [30, 30, 120, 50],
                    },
                    {
                        "id": "b2",
                        "page": 1,
                        "text": "Salary 456",
                        "language": "eng",
                        "bbox": [30, 70, 120, 90],
                    },
                ],
            },
        ],
        "tables": [
            {
                "id": "native-table",
                "page": 1,
                "bbox": [20, 20, 200, 200],
                "cells": [{"bbox": [20, 20, 200, 60], "text": ""}],
            }
        ],
    }


def test_geometry_only_table_uses_actual_blocks_as_one_atomic_unit():
    units = ContextPackBuilder(LocalTokenizerFixture()).units(table_ir())
    assert len(units) == 1 and units[0].kind == "table"
    assert units[0].block_ids == ("b1", "b2")


def test_private_table_translation_does_not_raise_keyerror_and_receives_domain():
    result, requests = run_private(table_ir())
    assert set(result["translations"]) == {"b1", "b2"}
    assert not result["issues"]
    assert requests[0]["document_context"]["domain"] == "BANKING"
    assert requests[0]["document_context"]["document_type"] == "bank_statement"
    assert "123" in result["translations"]["b1"]


def test_unmapped_table_is_reported_not_sent_as_an_invented_renderable_id():
    ir = table_ir()
    ir["tables"][0]["bbox"] = [300, 300, 400, 400]
    result, requests = run_private(ir)
    assert any(issue["code"] == "UNMAPPED_TABLE_CONTENT" for issue in result["issues"])
    assert set(result["translations"]) == {"b1", "b2"}
    assert all(
        not block["id"].startswith("table:") for request in requests for block in request["blocks"]
    )
