from io import BytesIO
from PIL import Image

from steamship import Block, File, MimeTypes, Steamship, Task


def main():
    with Steamship.temporary_workspace() as client:
        # create a file to serve as our "script" for this exercise
        # seed it with an initial prompt
        script = File.create(client, handle="test-script-001", content="script")
        script.append_block(text="portrait photo of a woman wearing traditional attire, photograph by Steve McCurry",
                            mime_type=MimeTypes.TXT)

        sd = client.use_plugin("stable-diffusion-replicate")
        pix2pix = client.use_plugin("instruct-pix-to-pix-replicate")

        print("generating original image...")
        img_task = sd.generate(input_file_id=script.id,
                               append_output_to_file=True,
                               output_file_id=script.id)

        img_task.wait()

        print("original image generated.")
        script.append_block(text="give her aviator sunglasses", mime_type=MimeTypes.TXT)

        print("generating modified image...")
        pix_task = pix2pix.generate(input_file_id=script.id, input_file_start_block_index=1)
        pix_task.wait(max_timeout_s=600)

        print("modified image generated.")

        orig_img_block = img_task.output.blocks[0]
        orig_img_bytes = orig_img_block.raw()
        orig_img = Image.open(BytesIO(orig_img_bytes))

        pix_img_block = pix_task.output.blocks[0]
        pix_img_bytes = pix_img_block.raw()
        pix_img = Image.open(BytesIO(pix_img_bytes))

        # show images
        orig_img.show("original")
        pix_img.show("modified")


if __name__ == "__main__":
    main()
