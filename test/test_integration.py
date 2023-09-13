"""Test dall-e generator plugin via integration tests."""

from filetype import filetype
from steamship import File, MimeTypes, Steamship, Block
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
    client = Steamship(profile="staging", workspace="eleven-airplane-2")
    generator = client.use_plugin(GENERATOR_HANDLE)
    generator.wait_for_init()

    rows = []
    for i in range(2):
        rows.append(f"This is sentence {i}.")
    text = "\n".join(rows)

    test_file = File.create(client)

    # b = Block.create(client, file_id=test_file.id, text="HI", public_data=True)
    # r = b.raw()

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

    with open('out.mpt', 'wb') as f2:
        f2.write(block.raw())

    url = f"https://api.staging.steamship.com/block/{block.id}/raw"

    print(url)


