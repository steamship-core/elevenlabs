"""Test dall-e generator plugin via integration tests."""

from steamship import Block, File, MimeTypes, Steamship
from steamship.invocable import InvocationContext
from steamship.plugin.inputs.raw_block_and_tag_plugin_input_with_preallocated_blocks import (
    RawBlockAndTagPluginInputWithPreallocatedBlocks,
)
from steamship.plugin.outputs.plugin_output import OperationType, OperationUnit
from steamship.plugin.request import PluginRequest

from api import ElevenlabsPlugin


def test_stream_into_block():
    """Tests streaming into a block"""
    with Steamship.temporary_workspace() as client:
        plugin = ElevenlabsPlugin(client, None, InvocationContext(invocable_instance_handle="foo"))

        text = "Hi there"
        f = File.create(client)
        output_block = Block.create(
            client, file_id=f.id, streaming=True, public_data=True, mime_type=MimeTypes.MP3
        )
        usage = plugin.stream_into_block(text, output_block)
        assert usage.operation_unit == OperationUnit.CHARACTERS
        assert usage.operation_type == OperationType.RUN
        assert usage.operation_amount == len(text)
        assert usage.audit_id == f"{client.config.api_base}block/{output_block.id}/raw"

        raw_value = output_block.raw()
        assert raw_value is not None


def test_stream_into_block_with_hindi():
    """Tests Hindi support."""
    with Steamship.temporary_workspace() as client:
        plugin = ElevenlabsPlugin(
            client,
            {"model_id": "eleven_multilingual_v1"},
            InvocationContext(invocable_instance_handle="foo"),
        )

        text = "साइकिल पर एक बिल्ली"
        f = File.create(client)
        output_block = Block.create(
            client, file_id=f.id, streaming=True, public_data=True, mime_type=MimeTypes.MP3
        )
        usage = plugin.stream_into_block(text, output_block)

        assert usage.operation_unit == OperationUnit.CHARACTERS
        assert usage.operation_type == OperationType.RUN
        assert usage.operation_amount == len(text)
        assert usage.audit_id == f"{client.config.api_base}block/{output_block.id}/raw"

        raw_value = output_block.raw()
        assert raw_value is not None


def test_generator_streaming():
    """Tests streaming into a block with the plugin interface that wraps the raw generation method."""
    with Steamship.temporary_workspace() as client:
        plugin = ElevenlabsPlugin(client, None, InvocationContext(invocable_instance_handle="foo"))

        text = "Hi there"
        f = File.create(client)
        output_block = Block.create(
            client, file_id=f.id, streaming=True, public_data=True, mime_type=MimeTypes.MP3
        )

        req = PluginRequest(
            data=RawBlockAndTagPluginInputWithPreallocatedBlocks(
                blocks=[Block(text=text)], output_blocks=[output_block]
            )
        )

        resp = plugin.run(req)

        assert len(resp.data.usage) == 1
        usage = resp.data.usage[0]

        assert usage.operation_unit == OperationUnit.CHARACTERS
        assert usage.operation_type == OperationType.RUN
        assert usage.operation_amount == len(text)
        assert usage.audit_id == f"{client.config.api_base}block/{output_block.id}/raw"

        raw_value = output_block.raw()
        assert raw_value is not None

        assert output_block.mime_type == MimeTypes.MP3
        assert output_block.url is None

        assert len(resp.data.usage) == 1
        assert resp.data.usage[0].operation_amount == len(text)
        assert resp.data.usage[0].operation_unit == OperationUnit.CHARACTERS
