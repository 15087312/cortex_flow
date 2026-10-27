"""Built-in skills with lazy-loadable handlers."""

from __future__ import annotations

import json
import re
from typing import Any

from cortexflow.skills.registry import SkillRegistry


async def _summarize_handler(text: str, max_length: int = 200, **kwargs: Any) -> dict[str, Any]:
    sentences = re.split(r'[.!?。！？]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return {"summary": "", "original_length": len(text), "summary_length": 0}

    scored = []
    for i, sent in enumerate(sentences):
        score = 0
        if i == 0:
            score += 3
        if i == len(sentences) - 1:
            score += 1
        score += min(len(sent) / 50, 3)
        if any(kw in sent for kw in ["重要", "关键", "总结", "因此", "所以", "important", "key", "therefore"]):
            score += 2
        scored.append((score, i, sent))

    scored.sort(key=lambda x: (-x[0], x[1]))

    result_sentences = []
    total_len = 0
    for _, idx, sent in sorted(scored, key=lambda x: x[1]):
        if total_len + len(sent) > max_length:
            break
        result_sentences.append(sent)
        total_len += len(sent)

    summary = "。".join(result_sentences) if result_sentences else sentences[0][:max_length]
    return {
        "summary": summary,
        "original_length": len(text),
        "summary_length": len(summary),
        "sentence_count": len(sentences),
    }


async def _extract_keywords_handler(text: str, top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
    stop_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "为什么",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "could", "should", "may", "might",
        "can", "shall", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below", "between", "and",
        "but", "or", "not", "no", "if", "then", "than", "so", "that", "this", "it",
    }

    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower())
    freq: dict[str, int] = {}
    for word in words:
        if word not in stop_words and len(word) > 1:
            freq[word] = freq.get(word, 0) + 1

    top_words = sorted(freq.items(), key=lambda x: -x[1])[:top_k]
    return {
        "keywords": [w for w, _ in top_words],
        "frequencies": dict(top_words),
        "total_words": len(words),
        "unique_words": len(freq),
    }


async def _translate_handler(
    text: str, source_lang: str = "auto", target_lang: str = "en", **kwargs: Any
) -> dict[str, Any]:
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    detected = "zh" if has_chinese else "en"
    actual_source = source_lang if source_lang != "auto" else detected

    return {
        "original": text,
        "detected_language": detected,
        "source_language": actual_source,
        "target_language": target_lang,
        "note": "Translation requires LLM adapter. Use model node for actual translation.",
        "text": text,
    }


async def _format_json_handler(data: Any, indent: int = 2, **kwargs: Any) -> dict[str, Any]:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"formatted": data, "error": "Input is not valid JSON"}

    formatted = json.dumps(data, indent=indent, ensure_ascii=False, default=str)
    return {"formatted": formatted, "type": type(data).__name__}


async def _text_stats_handler(text: str, **kwargs: Any) -> dict[str, Any]:
    chars = len(text)
    chars_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
    words = len(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]+', text))
    sentences = len(re.split(r'[.!?。！？]+', text)) - 1
    lines = text.count("\n") + 1
    paragraphs = len([p for p in text.split("\n\n") if p.strip()])

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))

    return {
        "characters": chars,
        "characters_no_spaces": chars_no_space,
        "words": words,
        "sentences": max(sentences, 1),
        "lines": lines,
        "paragraphs": max(paragraphs, 1),
        "chinese_characters": chinese_chars,
        "english_words": english_words,
        "estimated_tokens": chars // 2 if chinese_chars > english_words else words,
    }


async def _template_handler(
    template: str, variables: dict[str, Any] | None = None, **kwargs: Any
) -> dict[str, Any]:
    variables = variables or {}
    result = template
    for key, value in variables.items():
        result = result.replace(f"${{{key}}}", str(value))
        result = result.replace(f"{{{{{key}}}}}", str(value))

    remaining = re.findall(r'\$\{(\w+)\}|\{\{(\w+)\}\}', result)
    unresolved = [m[0] or m[1] for m in remaining]

    return {
        "rendered": result,
        "unresolved_variables": unresolved,
        "applied_variables": list(variables.keys()),
    }


async def _validate_handler(
    data: Any, rules: dict[str, Any] | None = None, **kwargs: Any
) -> dict[str, Any]:
    rules = rules or {}
    errors = []

    if "type" in rules:
        expected = rules["type"]
        type_map = {"string": str, "number": (int, float), "integer": int, "list": list, "dict": dict, "bool": bool}
        if expected in type_map and not isinstance(data, type_map[expected]):
            errors.append(f"Expected type '{expected}', got '{type(data).__name__}'")

    if "min_length" in rules and isinstance(data, (str, list)):
        if len(data) < rules["min_length"]:
            errors.append(f"Length {len(data)} is less than minimum {rules['min_length']}")

    if "max_length" in rules and isinstance(data, (str, list)):
        if len(data) > rules["max_length"]:
            errors.append(f"Length {len(data)} exceeds maximum {rules['max_length']}")

    if "pattern" in rules and isinstance(data, str):
        if not re.match(rules["pattern"], data):
            errors.append(f"Does not match pattern '{rules['pattern']}'")

    if "enum" in rules and data not in rules["enum"]:
        errors.append(f"Value '{data}' not in allowed values: {rules['enum']}")

    if "required_keys" in rules and isinstance(data, dict):
        for key in rules["required_keys"]:
            if key not in data:
                errors.append(f"Missing required key: '{key}'")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "data_type": type(data).__name__,
    }


async def _split_text_handler(
    text: str, chunk_size: int = 500, overlap: int = 50, separator: str = "\n", **kwargs: Any
) -> dict[str, Any]:
    if separator == "sentence":
        parts = re.split(r'(?<=[.!?。！？])\s*', text)
    elif separator == "paragraph":
        parts = text.split("\n\n")
    else:
        parts = text.split(separator)

    parts = [p.strip() for p in parts if p.strip()]

    chunks = []
    current_chunk = ""
    for part in parts:
        if len(current_chunk) + len(part) + 1 > chunk_size and current_chunk:
            chunks.append(current_chunk)
            if overlap > 0:
                words = current_chunk.split()
                overlap_text = " ".join(words[-max(1, len(words) // 5):])
                current_chunk = overlap_text + " " + part
            else:
                current_chunk = part
        else:
            current_chunk = current_chunk + "\n" + part if current_chunk else part

    if current_chunk:
        chunks.append(current_chunk)

    return {
        "chunks": chunks,
        "chunk_count": len(chunks),
        "chunk_sizes": [len(c) for c in chunks],
        "original_length": len(text),
    }


def register_builtin_skills(registry: SkillRegistry) -> None:
    registry.register(
        skill_id="summarize",
        name="文本摘要",
        description="将长文本压缩为简短摘要",
        handler=_summarize_handler,
        category="text",
        tags=["text", "summary", "compression"],
        triggers=["摘要", "总结", "summarize", "summary"],
        parameters={"text": "str", "max_length": "int = 200"},
    )

    registry.register(
        skill_id="extract_keywords",
        name="关键词提取",
        description="从文本中提取关键词",
        handler=_extract_keywords_handler,
        category="text",
        tags=["text", "keywords", "extraction"],
        triggers=["关键词", "关键字", "keywords", "extract keywords"],
        parameters={"text": "str", "top_k": "int = 10"},
    )

    registry.register(
        skill_id="translate",
        name="翻译助手",
        description="语言检测和翻译准备",
        handler=_translate_handler,
        category="text",
        tags=["text", "translation", "language"],
        triggers=["翻译", "translate", "translation"],
        parameters={"text": "str", "source_lang": "str = auto", "target_lang": "str = en"},
    )

    registry.register(
        skill_id="format_json",
        name="JSON 格式化",
        description="格式化和验证 JSON 数据",
        handler=_format_json_handler,
        category="data",
        tags=["data", "json", "format"],
        triggers=["json", "format json", "格式化"],
        parameters={"data": "Any", "indent": "int = 2"},
    )

    registry.register(
        skill_id="text_stats",
        name="文本统计",
        description="统计文本的字符数、词数、句子数等",
        handler=_text_stats_handler,
        category="text",
        tags=["text", "statistics", "analysis"],
        triggers=["统计", "字数", "statistics", "count"],
        parameters={"text": "str"},
    )

    registry.register(
        skill_id="template",
        name="模板渲染",
        description="使用变量渲染文本模板",
        handler=_template_handler,
        category="data",
        tags=["template", "render", "format"],
        triggers=["模板", "template", "render"],
        parameters={"template": "str", "variables": "dict"},
    )

    registry.register(
        skill_id="validate",
        name="数据验证",
        description="根据规则验证数据结构",
        handler=_validate_handler,
        category="data",
        tags=["validation", "data", "rules"],
        triggers=["验证", "validate", "check"],
        parameters={"data": "Any", "rules": "dict"},
    )

    registry.register(
        skill_id="split_text",
        name="文本分块",
        description="将长文本分割成指定大小的块",
        handler=_split_text_handler,
        category="text",
        tags=["text", "split", "chunk", "rag"],
        triggers=["分块", "分割", "split", "chunk"],
        parameters={"text": "str", "chunk_size": "int = 500", "overlap": "int = 50"},
    )
