"""Test dall-e generator plugin via integration tests."""

from filetype import filetype
from steamship import File, MimeTypes, Steamship

IMAGE_GENERATOR_HANDLE = "stable-diffusion-replicate"
MULTI_MODAL_GENERATOR_HANDLE = "instruct-pix-to-pix-replicate"


def test_generator():
    with Steamship.temporary_workspace() as client:
        sd = client.use_plugin(IMAGE_GENERATOR_HANDLE)

        test_file = File.create(client, handle="test-script", content="script")
        task = sd.generate(
            text="A cat on a bicycle",
            append_output_to_file=True,
            output_file_id=test_file.id,
            options={"size": "512x512", "negative_prompt": "water bottles"},
        )
        task.wait()

        test_file.append_block(text="give the cat a helmet")
        pix2pix = client.use_plugin(MULTI_MODAL_GENERATOR_HANDLE)
        pix_task = pix2pix.generate(input_file_id=test_file.id)
        pix_task.wait(max_timeout_s=600)

        block = pix_task.output.blocks[0]

        assert block is not None
        # check that Steamship thinks it is a PNG and that the bytes seem like a PNG
        assert block.mime_type == MimeTypes.JPG
        assert filetype.guess_mime(block.raw()) == MimeTypes.JPG
