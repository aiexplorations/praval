"""Edge contracts for registries, local providers, and storage helpers."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval.app import PravalApp
from praval.composition import run_agents as composition_run_agents
from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError, StateError
from praval.core.registry import PravalRegistry
from praval.core.secure_spore import SporeKeyManager
from praval.core.storage import StateStorage
from praval.models import ModelResponse, ProviderCapabilities, ProviderProfile
from praval.providers.factory import ProviderFactory
from praval.providers.openai_compatible import OpenAICompatibleProvider
from praval.providers.registry import (
    ProviderRegistry,
    _gemini_builder,
    _openai_compatible_builder,
)
from praval.storage.base_provider import (
    BaseStorageProvider,
    DataReference,
    StorageResult,
    StorageType,
)


def test_provider_registry_filters_alias_profiles_and_applies_known_overrides():
    registry = ProviderRegistry()
    builder = Mock(return_value="provider")
    registry.register_provider(
        "openai-compatible",
        builder,
        aliases=("ollama",),
        default_model="local-model",
        capabilities=ProviderCapabilities(streaming=True),
    )
    wildcard = ProviderProfile(
        provider="openai-compatible",
        model="*",
        capabilities=ProviderCapabilities(local=True),
    )
    exact = ProviderProfile(provider="other", model="model-b")
    registry.register_profile(wildcard)
    registry.register_profile(exact)

    assert registry.create_provider("ollama", "config") == "provider"
    builder.assert_called_once_with("config")
    assert registry.list_profiles("ollama") == [wildcard]
    capabilities = registry.resolve_capabilities(
        "ollama",
        "unknown",
        overrides={"streaming": True, "not_a_capability": True},
    )
    assert capabilities.local is True
    assert capabilities.streaming is True
    assert registry.default_model_for("ollama") == "local-model"


def test_lazy_provider_builders_construct_expected_adapters():
    config = object()
    with patch(
        "praval.providers.openai_compatible.OpenAICompatibleProvider",
        return_value="local",
    ) as local_class:
        assert _openai_compatible_builder(config) == "local"
    local_class.assert_called_once_with(config)

    with patch("praval.providers.gemini.GeminiProvider", return_value="gemini") as cls:
        assert _gemini_builder(config) == "gemini"
    cls.assert_called_once_with(config)


def test_provider_factory_distinguishes_import_failures():
    registry = Mock()
    registry.create_provider.side_effect = ImportError("optional SDK missing")
    with patch("praval.providers.factory.get_provider_registry", return_value=registry):
        with pytest.raises(ProviderError, match="Failed to import provider"):
            ProviderFactory.create_provider("optional", object())


def test_openai_compatible_provider_validates_configuration_and_redacts_errors(
    monkeypatch,
):
    with pytest.raises(ProviderError, match="require base_url"):
        OpenAICompatibleProvider(AgentConfig(provider="custom", model="model"))

    config = AgentConfig(
        provider="custom",
        model="model",
        base_url="http://localhost:9000/v1",
        api_key_env="LOCAL_KEY",
        timeout=3,
    )
    monkeypatch.setenv("LOCAL_KEY", "secret-key")
    client = Mock()
    with patch(
        "praval.providers.openai_compatible.openai.OpenAI", return_value=client
    ) as cls:
        provider = OpenAICompatibleProvider(config)
    assert provider.client is client
    assert cls.call_args.kwargs == {
        "api_key": "secret-key",
        "base_url": "http://localhost:9000/v1",
        "timeout": 3,
    }

    with patch(
        "praval.providers.openai_compatible.openai.OpenAI",
        side_effect=RuntimeError("token=secret-key"),
    ):
        with pytest.raises(ProviderError) as raised:
            OpenAICompatibleProvider(config)
    assert "secret-key" not in str(raised.value)

    for url, message in (
        ("http:///missing-host", "include a host"),
        ("http://169.254.1.1/v1", "link-local"),
    ):
        with pytest.raises(ProviderError, match=message):
            provider._validate_base_url(url)


class _StorageProvider(BaseStorageProvider):
    async def connect(self) -> bool:
        self.is_connected = True
        return True

    async def disconnect(self):
        self.is_connected = False

    async def store(self, resource, data, **kwargs):
        return StorageResult(success=True, data=data)

    async def retrieve(self, resource, **kwargs):
        if resource == "raise":
            raise RuntimeError("backend failed")
        return StorageResult(success=resource == "exists")

    async def query(self, resource, query, **kwargs):
        return StorageResult(success=True, data=query)

    async def delete(self, resource, **kwargs):
        return StorageResult(success=True)


@pytest.mark.asyncio
async def test_base_storage_defaults_and_reference_expiry():
    provider = _StorageProvider("memory", {})
    assert provider.metadata.storage_type == StorageType.KEY_VALUE
    assert await provider.exists("exists") is True
    assert await provider.exists("missing") is False
    assert await provider.exists("raise") is False
    unsupported = await provider.list_resources()
    assert unsupported.success is False

    reference = DataReference(
        provider="memory",
        storage_type=StorageType.KEY_VALUE,
        resource_id="record/1",
    )
    assert DataReference.from_uri(reference.to_uri()).resource_id == "record/1"
    assert reference.is_expired() is False
    reference.expires_at = datetime.now() - timedelta(seconds=1)
    assert reference.is_expired() is True


def test_state_storage_wraps_save_load_delete_and_list_errors(tmp_path):
    storage = StateStorage(str(tmp_path))
    with patch("builtins.open", side_effect=OSError("disk full")):
        with pytest.raises(StateError, match="Failed to save state"):
            storage.save("agent", [])

    state_path = tmp_path / "agent.json"
    state_path.write_text("not-json")
    with pytest.raises(StateError, match="Corrupted state file"):
        storage.load("agent")

    with patch("pathlib.Path.unlink", side_effect=OSError("locked")):
        with pytest.raises(StateError, match="Failed to delete state"):
            storage.delete("agent")

    with patch("pathlib.Path.glob", side_effect=OSError("unreadable")):
        with pytest.raises(StateError, match="Failed to list stored agents"):
            storage.list_agents()


def test_small_public_helpers_cover_closed_app_registry_copy_and_model_properties():
    app = PravalApp(reef=Mock(), provider_registry=Mock())
    app.close()
    with pytest.raises(RuntimeError, match="closed"):
        app.create_agent("late")

    registry = PravalRegistry()
    agent = SimpleNamespace(name="agent-a", tools={})
    registry.register_agent(agent)
    copied = registry.get_all_agents()
    copied.clear()
    assert registry.get_agent("agent-a") is agent

    capabilities = ProviderCapabilities(streaming=True)
    assert capabilities.supports("streaming") is True
    assert capabilities.supports("unknown") is False
    assert ModelResponse(content="text").text == "text"


def test_composition_run_agents_delegates_to_runner_implementation():
    worker = Mock()
    with patch("praval.composition._run_agents_impl", return_value="runner") as impl:
        assert (
            composition_run_agents(
                worker,
                backend_config={"url": "amqp://test"},
                channel_queue_map={"channel": "queue"},
            )
            == "runner"
        )
    impl.assert_called_once_with(
        worker,
        backend_config={"url": "amqp://test"},
        channel_queue_map={"channel": "queue"},
    )


def test_secure_spore_key_manager_wraps_serialization_and_verification_errors():
    manager = SporeKeyManager("agent-a")
    with patch(
        "praval.core.secure_spore.json.dumps",
        side_effect=TypeError("not serializable"),
    ):
        with pytest.raises(ValueError, match="Failed to encrypt"):
            manager.encrypt_and_sign({"bad": object()}, manager.public_key)

    with patch(
        "praval.core.secure_spore.nacl.signing.VerifyKey",
        side_effect=RuntimeError("invalid verifier"),
    ):
        with pytest.raises(ValueError, match="Failed to decrypt"):
            manager.decrypt_and_verify(b"data", b"nonce", b"sig", b"key", b"verify")
