from __future__ import annotations

from app.ai.context.builder import ContextPackBuilder, DocumentMemory


class SyntheticTokenizer:
    def encode(self, value: str, *, add_special_tokens: bool = False):
        return list(value)

    def apply_chat_template(self, messages, *, tokenize: bool, add_generation_prompt: bool):
        value = "".join(f"<{item['role']}>{item['content']}" for item in messages)
        return value + ("<assistant>" if add_generation_prompt else "")


def test_document_memory_is_caller_supplied_and_retrieved_as_bounded_fragments():
    builder = ContextPackBuilder(tokenizer=SyntheticTokenizer())
    chunk = {"blocks": [{"id": "b1", "text": "employment certificate"}]}
    context = builder.relevant_context(
        {},
        chunk,
        {
            "document_memory": DocumentMemory(
                document_type="employment_certificate",
                domain="HR",
                terminology=(
                    {"source": "employment certificate", "target": "attestation de travail"},
                ),
            ).__dict__,
        },
    )

    assert context["document"][0]["document_type"] == "employment_certificate"
    assert context["document_memory"][0]["target"] == "attestation de travail"
    assert "pages" not in str(context)


def test_message_count_uses_actual_chat_template_without_model_download():
    builder = ContextPackBuilder(tokenizer=SyntheticTokenizer())
    messages = [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": '{"blocks":[]}'},
    ]
    expected = len('<system>instructions<user>{"blocks":[]}<assistant>')
    assert builder.count_messages(messages) == expected
