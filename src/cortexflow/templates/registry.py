"""Template registry with built-in workflow templates."""

from __future__ import annotations

from typing import Any


class TemplateRegistry:
    """Registry for workflow templates."""

    def __init__(self):
        self._templates: dict[str, dict[str, Any]] = {}
        self._register_builtins()

    def register(self, template_id: str, template: dict[str, Any]) -> None:
        """Register a template."""
        self._templates[template_id] = template

    def get(self, template_id: str) -> dict[str, Any] | None:
        """Get a template."""
        return self._templates.get(template_id)

    def list(self) -> list[str]:
        """List template IDs."""
        return list(self._templates.keys())

    def list_all(self) -> dict[str, dict[str, Any]]:
        """List all templates."""
        return dict(self._templates)

    def unregister(self, template_id: str) -> None:
        """Unregister a template."""
        self._templates.pop(template_id, None)

    def _register_builtins(self) -> None:
        self.register("sequential_flow", {
            "id": "sequential_flow",
            "name": "Sequential Flow",
            "description": "Execute nodes in sequence",
            "definition": {
                "id": "sequential",
                "name": "Sequential Flow",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "step_1",
                "nodes": {
                    "step_1": {
                        "type": "model",
                        "tier": "default",
                        "identity": "assistant",
                        "custom_system": "Process the input.",
                        "input": {"data": "${input}"},
                        "output": "step_1_result",
                        "on_success": "step_2",
                    },
                    "step_2": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": "${step_1_result}"},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })

        self.register("parallel_flow", {
            "id": "parallel_flow",
            "name": "Parallel Flow",
            "description": "Execute branches in parallel",
            "definition": {
                "id": "parallel",
                "name": "Parallel Flow",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "parallel_exec",
                "nodes": {
                    "parallel_exec": {
                        "type": "parallel",
                        "branches": ["branch_a", "branch_b"],
                        "strategy": "all",
                        "on_success": "merge",
                    },
                    "branch_a": {
                        "type": "model",
                        "tier": "default",
                        "identity": "worker_a",
                        "custom_system": "Handle part A.",
                        "input": {"data": "${input}"},
                        "output": "result_a",
                        "on_success": "__end__",
                    },
                    "branch_b": {
                        "type": "model",
                        "tier": "default",
                        "identity": "worker_b",
                        "custom_system": "Handle part B.",
                        "input": {"data": "${input}"},
                        "output": "result_b",
                        "on_success": "__end__",
                    },
                    "merge": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": {"a": "${result_a}", "b": "${result_b}"}},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })

        self.register("map_reduce_flow", {
            "id": "map_reduce_flow",
            "name": "Map-Reduce Flow",
            "description": "Map over items then reduce",
            "definition": {
                "id": "map_reduce",
                "name": "Map-Reduce Flow",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "map_step",
                "nodes": {
                    "map_step": {
                        "type": "map",
                        "collection": "${items}",
                        "element_var": "item",
                        "map_body": "process_item",
                        "output_collection": "mapped",
                        "on_success": "reduce_step",
                    },
                    "process_item": {
                        "type": "model",
                        "tier": "default",
                        "identity": "processor",
                        "custom_system": "Process this item.",
                        "input": {"item": "${item}"},
                        "output": "processed",
                        "on_success": "__end__",
                    },
                    "reduce_step": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": "${mapped}"},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })

        self.register("loop_flow", {
            "id": "loop_flow",
            "name": "Loop Flow",
            "description": "Iterate with a loop node",
            "definition": {
                "id": "loop",
                "name": "Loop Flow",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "loop_step",
                "nodes": {
                    "loop_step": {
                        "type": "loop",
                        "loop_mode": "foreach",
                        "items": "${items}",
                        "item_var": "current",
                        "body": "process",
                        "on_success": "finalize",
                    },
                    "process": {
                        "type": "model",
                        "tier": "default",
                        "identity": "processor",
                        "custom_system": "Process the current item.",
                        "input": {"item": "${current}"},
                        "output": "processed_item",
                        "on_success": "__end__",
                    },
                    "finalize": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": "done"},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })

        self.register("rag_flow", {
            "id": "rag_flow",
            "name": "RAG Flow",
            "description": "Retrieval-Augmented Generation: search knowledge base then generate answer",
            "definition": {
                "id": "rag_pipeline",
                "name": "RAG Pipeline",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "retrieve",
                "tiers": {
                    "default": {
                        "model": "gpt-4o",
                        "provider": "openai",
                    },
                },
                "variables": {
                    "question": {
                        "type": "string",
                        "required": True,
                        "description": "User question to answer",
                    },
                },
                "nodes": {
                    "retrieve": {
                        "type": "retrieval",
                        "retrieval_query": "${question}",
                        "retrieval_source": "knowledge_base",
                        "retrieval_top_k": 3,
                        "output": "docs",
                        "on_success": "generate",
                    },
                    "generate": {
                        "type": "model",
                        "tier": "default",
                        "identity": "assistant",
                        "custom_system": "You are a helpful assistant. Use the provided context documents to answer the user's question accurately. If the context doesn't contain relevant information, say so.",
                        "input": {
                            "question": "${question}",
                            "context": "${docs}",
                        },
                        "output": "answer",
                        "on_success": "format",
                    },
                    "format": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": "${answer}"},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })

        self.register("memory_conversation", {
            "id": "memory_conversation",
            "name": "Memory Conversation",
            "description": "AI conversation with long-term memory: recall context, respond, then save summary",
            "definition": {
                "id": "memory_chat",
                "name": "Memory-Augmented Chat",
                "version": "1.0.0",
                "config": {"default_tier": "default", "role": "assistant"},
                "entry": "recall",
                "tiers": {
                    "default": {
                        "model": "gpt-4o",
                        "provider": "openai",
                    },
                },
                "variables": {
                    "user_message": {
                        "type": "string",
                        "required": True,
                        "description": "User message",
                    },
                },
                "nodes": {
                    "recall": {
                        "type": "memory",
                        "memory_action": "query",
                        "memory_content": "${user_message}",
                        "memory_namespace": "conversation_history",
                        "memory_top_k": 5,
                        "output": "context",
                        "on_success": "respond",
                    },
                    "respond": {
                        "type": "model",
                        "tier": "default",
                        "identity": "assistant",
                        "custom_system": "You are a helpful assistant with memory of past conversations. Use the recalled context to provide personalized, contextually-aware responses.",
                        "input": {
                            "message": "${user_message}",
                            "recalled_context": "${context}",
                        },
                        "output": "response",
                        "on_success": "remember",
                    },
                    "remember": {
                        "type": "memory",
                        "memory_action": "store",
                        "memory_content": "${response}",
                        "memory_namespace": "conversation_history",
                        "on_success": "finalize",
                    },
                    "finalize": {
                        "type": "state",
                        "actions": [
                            {"action": "set", "target": "result", "value": "${response}"},
                        ],
                        "on_success": "__end__",
                    },
                },
            },
        })
