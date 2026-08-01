"""Provider-neutral interpretation boundary and deterministic test providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .interpretation_models import (
    INTERPRETATION_PROVIDER_CONTRACT_REVISION,
    InterpretationProviderRequest,
    InterpretationProviderResponse,
)


@dataclass(frozen=True)
class InterpretationProviderMetadata:
    provider_id: str
    provider_kind: str
    model_id: str
    model_revision: str
    provider_contract_revision: str = INTERPRETATION_PROVIDER_CONTRACT_REVISION
    supports_seed: bool = False
    supports_structured_output: bool = True
    supports_response_schema: bool = True
    supports_data_residency_metadata: bool = False
    maximum_input_characters: int = 20_000
    maximum_output_items: int = 500


class InterpretationProvider(ABC):
    metadata: InterpretationProviderMetadata

    @abstractmethod
    def interpret(
        self, request: InterpretationProviderRequest
    ) -> InterpretationProviderResponse:
        raise NotImplementedError


class RecordedFixtureInterpretationProvider(InterpretationProvider):
    def __init__(
        self,
        fixture_responses: dict[str, list[dict[str, Any]]],
        *,
        provider_id: str = "recorded_fixture_v1",
        model_id: str = "recorded_fixture_model",
        model_revision: str = "fixture_1",
    ) -> None:
        self.fixture_responses = fixture_responses
        self.metadata = InterpretationProviderMetadata(
            provider_id=provider_id,
            provider_kind="recorded_fixture",
            model_id=model_id,
            model_revision=model_revision,
        )

    def interpret(
        self, request: InterpretationProviderRequest
    ) -> InterpretationProviderResponse:
        items = self.fixture_responses.get(request.interpretation_request_id)
        if items is None:
            items = self.fixture_responses.get("*", [])
        return InterpretationProviderResponse(
            provider_request_id=f"recorded_{request.interpretation_request_id}",
            status="completed",
            items=tuple(items),
        )


class NullInterpretationProvider(InterpretationProvider):
    def __init__(self) -> None:
        self.metadata = InterpretationProviderMetadata(
            provider_id="null_provider_v1",
            provider_kind="null",
            model_id="none",
            model_revision="none",
            supports_structured_output=False,
            supports_response_schema=False,
            maximum_output_items=0,
        )

    def interpret(
        self, request: InterpretationProviderRequest
    ) -> InterpretationProviderResponse:
        return InterpretationProviderResponse(
            provider_request_id=None,
            status="provider_unavailable",
            error_code="INTERPRETATION_PROVIDER_UNAVAILABLE",
        )


__all__ = [
    "InterpretationProvider",
    "InterpretationProviderMetadata",
    "NullInterpretationProvider",
    "RecordedFixtureInterpretationProvider",
]
