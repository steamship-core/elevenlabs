"""Test dall-e generator plugin via integration tests."""

from filetype import filetype
from steamship import File, MimeTypes, Steamship

GENERATOR_HANDLE = "elevenlabs-ted"


def test_streaming_audio():
    with Steamship.temporary_workspace() as client:
        generator = client.use_plugin(GENERATOR_HANDLE)

        test_file = File.create(client, handle="test-script", content="script")
        task = generator.generate(
            text="Hello there! This response was generated with streaming!",
            append_output_to_file=True,
            output_file_id=test_file.id,
        )
        task.wait()

        test_file = test_file.refresh()

        block = test_file.blocks[0]

        assert block is not None
        assert block.mime_type == MimeTypes.MP3

        with open("foo.mp3", "wb") as f:
            f.write(block.raw())
