"""Test dall-e generator plugin via integration tests."""

from steamship import File, MimeTypes, Steamship, Block
from steamship.invocable import InvocationContext
from steamship.plugin.inputs.raw_block_and_tag_plugin_input import RawBlockAndTagPluginInput
from steamship.plugin.outputs.plugin_output import OperationUnit
from steamship.plugin.request import PluginRequest

from api import ElevenlabsPlugin


def test_generator():
    with Steamship.temporary_workspace() as client:
        plugin = ElevenlabsPlugin(client, None, InvocationContext(
            invocable_instance_handle="foo"
        ))

        text = "Hi there"
        req = PluginRequest(data=RawBlockAndTagPluginInput(
            blocks=[
                Block(text=text)
            ]
        ))

        resp = plugin.run(req)

        assert resp.data.blocks is not None
        block = resp.data.blocks[0]

        assert block is not None

        # check that Steamship thinks it is a PNG and that the bytes seem like a PNG
        assert block.mime_type == MimeTypes.MP3


        assert len(resp.data.usage) == 1
        assert resp.data.usage[0].operation_amount == len(text)
        assert resp.data.usage[0].operation_unit == OperationUnit.CHARACTERS

