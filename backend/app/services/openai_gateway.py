"""Backward-compatible import for the new provider-aware gateway."""

from .ai_gateway import AIGateway as OpenAIGateway

__all__ = ["OpenAIGateway"]
