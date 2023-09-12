"""Test dall-e generator plugin via integration tests."""

from filetype import filetype
from steamship import File, MimeTypes, Steamship
from time import sleep

GENERATOR_HANDLE = "elevenlabs-ted"


def test_streaming_audio():
    with Steamship.temporary_workspace() as client:
        generator = client.use_plugin(GENERATOR_HANDLE)

        test_file = File.create(client, handle="test-script", content="script")
        task = generator.generate(
            text="Hello there! This response was generated with streaming!",
            append_output_to_file=True,
            output_file_id=test_file.id,
            make_output_public=True
        )

        task.wait()

        test_file = test_file.refresh()
        block = test_file.blocks[0]

        assert block is not None
        assert block.mime_type == MimeTypes.MP3
        assert block.public_data


def test_streaming_audio_long():
    client = Steamship(profile="test")
    generator = client.use_plugin(GENERATOR_HANDLE)

    rows = []
    for i in range(100):
        rows.append(f"This is sentence {i}.")
    text = "\n".join(rows)

    test_file = File.create(client)
    task = generator.generate(
        text="Hello there! This response was generated with streaming!",
        append_output_to_file=True,
        output_file_id=test_file.id,
        make_output_public=True
    )
    sleep(2)

    test_file = test_file.refresh()

    block = test_file.blocks[0]
    
    # It's public
    assert block is not None
    assert block.public_data

    url = f"https://api.staging.steamship.com/block/{block.id}/raw"

    print(url)


