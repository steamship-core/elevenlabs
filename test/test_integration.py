"""Test dall-e generator plugin via integration tests."""

from time import sleep

from steamship import File, Steamship

GENERATOR_HANDLE = "elevenlabs-ted"


def test_streaming_audio_long():
    client = Steamship(profile="staging", workspace="eleven-airplane-4")
    generator = client.use_plugin(GENERATOR_HANDLE)
    generator.wait_for_init()

    test_file = File.create(client)

    task = generator.generate(
        text="Hello there! This response was generated with streaming!",
        append_output_to_file=True,
        output_file_id=test_file.id,
        make_output_public=True,
    )
    assert task.task_id

    sleep(2)

    test_file = test_file.refresh()

    block = test_file.blocks[0]

    # It's public
    assert block is not None
    assert block.public_data

    url = f"https://api.staging.steamship.com/api/v1/block/{block.id}/raw"

    print(url)
