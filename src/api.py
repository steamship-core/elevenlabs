"""Generator plugin for Stable Diffusion running on replicate.com."""
import io
import json
import logging
import time
from typing import Any, Dict, Type, Union

import requests
from pydantic import Field
from steamship import Block, File, MimeTypes, Steamship, SteamshipError, Task, TaskState, Tag
from steamship.data import TagKind
from steamship.data.block import BlockUploadType
from steamship.data.workspace import SignedUrl
from steamship.invocable import Config, InvocableResponse, InvocationContext
from steamship.plugin.generator import Generator
from steamship.plugin.inputs.raw_block_and_tag_plugin_input import RawBlockAndTagPluginInput
from steamship.plugin.outputs.plugin_output import UsageReport, OperationType, OperationUnit
from steamship.plugin.outputs.raw_block_and_tag_plugin_output import RawBlockAndTagPluginOutput
from steamship.plugin.request import PluginRequest
from steamship.utils.signed_urls import upload_to_signed_url

import uuid


class ElevenlabsPluginConfig(Config):
    """Configuration for the InstructPix2Pix Plugin."""

    elevenlabs_api_key: str = Field(
        "",
        description="API key to use for Elevenlabs. Default uses Steamship's API key."
    )
    voice_id: str = Field(
        "21m00Tcm4TlvDq8ikWAM",
        description="Voice ID to use. Defaults to Rachel (21m00Tcm4TlvDq8ikWAM)"
    )
    stability: float = Field(0.5, description="")
    similarity_boost: float = Field(0.8, description="")


def save_audio(client: Steamship, filepath: str, audio: bytes) -> str:
    """Saves audio bytes to the user's workspace."""

    logging.info(f"ElevenLabsGenerator:save_audio - filename={filepath}")

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

    get_url_resp = workspace.create_signed_url(
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


def create_usage_report(input_text: str, for_url: str) -> UsageReport:
    characters = len(input_text)
    return UsageReport(
        operation_type=OperationType.RUN,
        operation_unit=OperationUnit.CHARACTERS,
        operation_amount=characters,
        audit_id=for_url
    )


def generate_audio(input_text: str, audit_url: str, config: ElevenlabsPluginConfig) -> (bytes, UsageReport):
    data = {
        "text": input_text,
        "voice_settings": {
            "stability": config.stability,
            "similarity_boost": config.similarity_boost
        }
    }

    headers = {
        'xi-api-key': f"{config.elevenlabs_api_key}",
        'Content-Type': 'application/json'
    }

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.voice_id}"
    logging.debug(f"Making request to {url}")

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        _bytes = response.content
        usage = create_usage_report(input_text, audit_url)
        return _bytes, usage
    else:
        raise SteamshipError(f"Received status code {response.status_code} from Eleven Labs. Reason: {response.reason}")


class ElevenlabsPlugin(Generator):
    """Eleven Labs Text-to-Speech generator."""

    config: ElevenlabsPluginConfig

    @classmethod
    def config_cls(cls) -> Type[Config]:
        """Return configuration template for the generator."""
        return ElevenlabsPluginConfig

    def run(
            self, request: PluginRequest[RawBlockAndTagPluginInput]
    ) -> InvocableResponse[RawBlockAndTagPluginOutput]:

        if not self.config.voice_id:
            raise SteamshipError(message=f"Must provide an Eleven Labs voice_id")

        if not self.context.invocable_instance_handle:
            raise SteamshipError(message="Empty invocable_instance_handle was provided; unable to save audio file.")

        into_filename = f"{self.context.invocable_instance_handle}/{str(uuid.uuid4())}.mp3"

        prompt_text = " ".join([block.text for block in request.data.blocks if block.text is not None])

        start_time = time.time()
        _bytes, usage = generate_audio(prompt_text, into_filename, self.config)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.debug(f"Retrieved audio data in f{elapsed_time}")

        blocks = [
            Block(content=_bytes, mime_type=MimeTypes.MP3, upload_type=BlockUploadType.FILE)
        ]

        # url = save_audio(self.client, into_filename, _bytes)
        # blocks = [
        #     Block(
        #         url=url,
        #         mime_type=MimeTypes.MP3,
        #         upload_type=BlockUploadType.URL,
        #         tags=[
        #             Tag(kind=TagKind.GENERATION, name="text-to-audio")
        #         ]
        #     )
        # ]
        usages = [
            usage
        ]
        return InvocableResponse(
            data=RawBlockAndTagPluginOutput(
                blocks=blocks,
                usage=usages
            ),
        )
