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
from steamship.plugin.outputs.block_type_plugin_output import BlockTypePluginOutput
from steamship.plugin.inputs.raw_block_and_tag_plugin_input_with_preallocated_blocks import (
    RawBlockAndTagPluginInputWithPreallocatedBlocks,
)

from steamship.plugin.outputs.stream_complete_plugin_output import StreamCompletePluginOutput
from steamship.plugin.request import PluginRequest
from steamship.plugin.streaming_generator import StreamingGenerator

import uuid


def save_audio(client: Steamship, plugin_instance_id: str, audio: bytes) -> str:
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


class ElevenlabsPluginConfig(Config):
    """Configuration for the ElevenLabs Plugin."""

    elevenlabs_api_key: str = Field(
        "",
        description="API key to use for Elevenlabs. Default uses Steamship's API key."
    )
    voice_id: str = Field(
        "21m00Tcm4TlvDq8ikWAM",
        description="Voice ID to use. Defaults to Rachel (21m00Tcm4TlvDq8ikWAM)"
    )
    model_id: str = Field(
        "eleven_monolingual_v1",
        description="Model ID to use. Defaults to eleven_monolingual_v1. Also available: eleven_multilingual_v1"
    )
    stability: float = Field(0.5, description="")
    similarity_boost: float = Field(0.8, description="")
    optimize_streaming_latency: int = Field(0, description="[Optional] An integer from [0,4]. How much to optimize for latency. 0 (Default) is no optimization with highest quality. 4 is lowest latency but may mispronounce words.")


def create_usage_report(input_text: str, for_url: str) -> UsageReport:
    characters = len(input_text)
    return UsageReport(
        operation_type=OperationType.RUN,
        operation_unit=OperationUnit.CHARACTERS,
        operation_amount=characters,
        audit_id=for_url
    )


def generate_audio_stream(input_text: str, audit_url: str, config: ElevenlabsPluginConfig) -> (bytes, UsageReport):
    data = {
        "text": input_text,
        "model_id": config.model_id,
        "voice_settings": {
            "stability": config.stability,
            "similarity_boost": config.similarity_boost,
        }
    }

    headers = {
        'xi-api-key': f"{config.elevenlabs_api_key}",
        'Content-Type': 'application/json',
        'accept': 'audio/mpeg'
    }

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.voice_id}/stream?optimize_streaming_latency={config.optimize_streaming_latency}"
    logging.debug(f"Making request to {url}")

    response = requests.post(url, json=data, headers=headers, stream=True)

    if response.status_code == 200:
        usage = create_usage_report(input_text, audit_url)
        return response.iter_content(), usage
    else:
        raise SteamshipError(f"Received status code {response.status_code} from Eleven Labs. Reason: {response.reason}")



class ElevenlabsPlugin(StreamingGenerator):
    """Eleven Labs Text-to-Speech generator."""

    config: ElevenlabsPluginConfig

    @classmethod
    def config_cls(cls) -> Type[Config]:
        """Return configuration template for the generator."""
        return ElevenlabsPluginConfig

    def determine_output_block_types(
        self, request: PluginRequest[RawBlockAndTagPluginInput]
    ) -> InvocableResponse[BlockTypePluginOutput]:
        """For Streaming operation.
        
        We stream into a single block. A future version of this plugin may generate multiple streams in
        parallel for multi-block input.
        """
        result = [MimeTypes.MP3.value]
        return InvocableResponse(data=BlockTypePluginOutput(block_types_to_create=result))

    def run(
        self, request: PluginRequest[RawBlockAndTagPluginInputWithPreallocatedBlocks]
    ) -> InvocableResponse[StreamCompletePluginOutput]:

        if not self.config.voice_id:
            raise SteamshipError(message=f"Must provide an Eleven Labs voice_id")

        if not self.context.invocable_instance_handle:
            raise SteamshipError(message="Empty invocable_instance_handle was provided; unable to save audio file.")

        if not request.data.output_blocks:
            raise SteamshipError(message="Empty output blocks structure was provided. Need at least one to stream into.")

        if not len(request.data.output_blocks) > 1:
            raise SteamshipError(message="More than one output block provided. This plugin assumes only one output block.")

        # Prepare data

        output_block = request.data.output_blocks[i]
        prompt_text = " ".join([block.text for block in request.data.blocks if block.text is not None])
        audit_url = f"https://api.steamship.com/api/v1/block/{output_block.id}/raw"

        # Begin Streaming

        start_time = time.time()
        
        _stream, usage = generate_audio_stream(prompt_text, audit_url, self.config)
        for chunk in _stream:
            output_block.append_stream(bytes=chunk)
        output_block.finish_stream()
        end_time = time.time()

        # Some light logging

        elapsed_time = end_time - start_time
        logging.debug(f"Completed audio stream in f{elapsed_time}")

        # Return a sync result
        # TODO: How do we report

        usages = [
            usage
        ]
        return InvocableResponse(
            data=StreamCompletePluginOutput(
                usage=usages
            ),
        )


