"""Generator plugin for Stable Diffusion running on replicate.com."""
import io
import json
import logging
import time
from typing import Any, Dict, Type, Union

import requests
from pydantic import Field
from steamship import Block, File, MimeTypes, Steamship, SteamshipError, Task, TaskState
from steamship.data.block import BlockUploadType
from steamship.invocable import Config, InvocableResponse, InvocationContext
from steamship.plugin.generator import Generator
from steamship.plugin.inputs.raw_block_and_tag_plugin_input import RawBlockAndTagPluginInput
from steamship.plugin.outputs.raw_block_and_tag_plugin_output import RawBlockAndTagPluginOutput
from steamship.plugin.request import PluginRequest
from steamship.utils.signed_urls import upload_to_signed_url

import uuid

def save_audio(self, client: Steamship, plugin_instance_id: str, audio: bytes) -> str:
    """Saves audio bytes to the user's workspace."""

    # generate a UUID and convert it to a string
    uuid_str = str(uuid.uuid4())
    filename = f"{uuid_str}.mp4"

    if plugin_instance_id is None:
        raise SteamshipError(message="Empty plugin_instance_id was provided; unable to save audio file.")

    filepath = f"{plugin_instance_id}/{filename}"

    logging.info(f"ElevenLabsGenerator:save_audio - filename={filename}")

    if bytes is None:
        raise SteamshipError(message="Empty bytes returned.")
    
    workspace = client.get_workspace()

    signed_url_resp = workspace.create_signed_url(
        SignedUrl.Request(
            bucket=SignedUrl.Bucket.PLUGIN_DATA,
            filepath=filepath,
            operation=SignedUrl.Operation.WRITE,
        )
    )

    if not signed_url_resp:
        raise SteamshipError(
            message="Empty result on Signed URL request while uploading model checkpoint"
        )
    if not signed_url_resp.signed_url:
        raise SteamshipError(
            message="Empty signedUrl on Signed URL request while uploading model checkpoint"
        )

    upload_to_signed_url(
        signed_url_resp.signed_url, 
        _bytes=audio
    )

    get_url_resp = self.workspace.create_signed_url(
        SignedUrl.Request(
            bucket=SignedUrl.Bucket.PLUGIN_DATA,
            filepath=filepath,
            operation=SignedUrl.Operation.READ,
        )
    )

    if not get_url_resp:
        raise SteamshipError(
            message="Empty result on Download Signed URL request while uploading model checkpoint"
        )
    if not get_url_resp.signed_url:
        raise SteamshipError(
            message="Empty signedUrl on Download Signed URL request while uploading model checkpoint"
        )

    return get_url_resp.signed_url


class ElevenlabsPlugin(Generator):
    """Eleven Labs Text-to-Speech generator."""

    class ElevenlabsPluginConfig(Config):
        """Configuration for the InstructPix2Pix Plugin."""

        elevenlabs_api_key: str = Field("",
                                       description="API key to use for Elevenlabs. Default uses Steamship's API key.")
        voice_id: str = Field("", description="Voice ID to use")
        stability: float = Field(0, description="")
        similarity_boost: float = Field(0, description="")

    @classmethod
    def config_cls(cls) -> Type[Config]:
        """Return configuration template for the generator."""
        return cls.ElevenlabsPluginConfig

    config: ElevenlabsPluginConfig

    def __init__(
            self,
            client: Steamship = None,
            config: Dict[str, Any] = None,
            context: InvocationContext = None,
    ):
        super().__init__(client, config, context)

    def run(
            self, request: PluginRequest[RawBlockAndTagPluginInput]
    ) -> InvocableResponse[RawBlockAndTagPluginOutput]:
        """Run the image generator against all the text, combined."""
        logging.info(f"request: {request}")
        return self._start_work(request)

    def _start_work(
            self, request: PluginRequest[RawBlockAndTagPluginInput]
    ) -> Union[InvocableResponse, InvocableResponse[RawBlockAndTagPluginOutput]]:
        logging.debug("starting generation...")

        options = request.data.options

        prompt_text = " ".join([block.text for block in request.data.blocks if block.text is not None])

        post_body = {
            "text": prompt_text,
            "voice_settings": {
                "stability": self.config.stability,
                "similarity_boost": self.config.similarity_boost
            }
        }

        headers = {
            'Authorization': f"Bearer {self.config.elevenlabs_api_key}",
            'Content-Type': 'application/json'
        }

        # send the POST request with the JSON data and headers
        start_time = time.time() 

        response = requests.post(url, json=data, headers=headers)

        end_time = time.time() 
        elapsed_time = end_time - start_time

        # retrieve the audio data from the response
        if response.status_code == 200:
            logging.debug(f"Retrieved audio data in f{elapsed_time}")
            audio_data = response.content
            url = save_audio(self.client, self.context.plugin_instance_id, audio_data)
            blocks = [
                Block(url=url, mime_type=MimeTypes.MP3, upload_type=BlockUploadType.URL)
            ]
            return InvocableResponse(data=RawBlockAndTagPluginOutput(blocks=blocks))

        else:
            raise SteamshipError(f"Received status code {response.status_code} from Eleven Labs. Reason: {response.reason}")
            
