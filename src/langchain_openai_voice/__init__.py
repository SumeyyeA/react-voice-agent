import asyncio
import json
import websockets

from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Any, Callable, Coroutine
from langchain_openai_voice.utils import amerge

from langchain_core.tools import BaseTool
from langchain_core._api import beta
from langchain_core.utils import secret_from_env

from pydantic import BaseModel, Field, SecretStr, PrivateAttr

import base64
from server.utils import is_speech


DEFAULT_MODEL = "gpt-4o-realtime-preview-2024-12-17"
DEFAULT_URL = "wss://api.openai.com/v1/realtime"

EVENTS_TO_IGNORE = {
    "response.function_call_arguments.delta",
    "rate_limits.updated",
    "response.audio_transcript.delta",
    "response.created",
    "response.content_part.added",
    "response.content_part.done",
    "conversation.item.created",
    "response.audio.done",
    "session.created",
    "session.updated",
    "response.done",
    "response.output_item.done",
}


@asynccontextmanager
async def connect(*, api_key: str, model: str, url: str) -> AsyncGenerator[
    tuple[
        Callable[[dict[str, Any] | str], Coroutine[Any, Any, None]],
        AsyncIterator[dict[str, Any]],
    ],
    None,
]:

    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    url = url or DEFAULT_URL
    url += f"?model={model}"

    websocket = await websockets.connect(url, extra_headers=headers)
    

    try:

        async def send_event(event: dict[str, Any] | str) -> None:
            formatted_event = json.dumps(event) if isinstance(event, dict) else event
            await websocket.send(formatted_event)

        async def event_stream() -> AsyncIterator[dict[str, Any]]:
            async for raw_event in websocket:
                yield json.loads(raw_event)

        stream: AsyncIterator[dict[str, Any]] = event_stream()

        yield send_event, stream
    finally:
        await websocket.close()


class VoiceToolExecutor(BaseModel):
    """
    Can accept function calls and emits function call outputs to a stream.
    """

    tools_by_name: dict[str, BaseTool]
    _trigger_future: asyncio.Future = PrivateAttr(default_factory=asyncio.Future)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _trigger_func(self) -> dict:  # returns a tool call
        return await self._trigger_future

    async def add_tool_call(self, tool_call: dict) -> None:
        # lock to avoid simultaneous tool calls racing and missing
        # _trigger_future being
        async with self._lock:
            if self._trigger_future.done():
                # TODO: handle simultaneous tool calls better
                raise ValueError("Tool call adding already in progress")

            self._trigger_future.set_result(tool_call)

    async def _create_tool_call_task(self, tool_call: dict) -> asyncio.Task[dict]:
        tool = self.tools_by_name.get(tool_call["name"])
        if tool is None:
            # immediately yield error, do not add task
            raise ValueError(
                f"tool {tool_call['name']} not found. "
                f"Must be one of {list(self.tools_by_name.keys())}"
            )

        # try to parse args
        try:
            args = json.loads(tool_call["arguments"])
        except json.JSONDecodeError:
            raise ValueError(
                f"failed to parse arguments `{tool_call['arguments']}`. Must be valid JSON."
            )

        async def run_tool() -> dict:
            result = await tool.ainvoke(args)
            try:
                result_str = json.dumps(result)
            except TypeError:
                # not json serializable, use str
                result_str = str(result)
            return {
                "type": "conversation.item.create",
                "item": {
                    "id": tool_call["call_id"],
                    "call_id": tool_call["call_id"],
                    "type": "function_call_output",
                    "output": result_str,
                },
            }

        task = asyncio.create_task(run_tool())
        return task

    async def output_iterator(self) -> AsyncIterator[dict]:  # yield events
        trigger_task = asyncio.create_task(self._trigger_func())
        tasks = set([trigger_task])
        while True:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                tasks.remove(task)
                if task == trigger_task:
                    async with self._lock:
                        self._trigger_future = asyncio.Future()
                    trigger_task = asyncio.create_task(self._trigger_func())
                    tasks.add(trigger_task)
                    tool_call = task.result()
                    try:
                        new_task = await self._create_tool_call_task(tool_call)
                        tasks.add(new_task)
                    except ValueError as e:
                        yield {
                            "type": "conversation.item.create",
                            "item": {
                                "id": tool_call["call_id"],
                                "call_id": tool_call["call_id"],
                                "type": "function_call_output",
                                "output": (f"Error: {str(e)}"),
                            },
                        }
                else:
                    yield task.result()


@beta()
class OpenAIVoiceReactAgent(BaseModel):
    model: str
    api_key: SecretStr = Field(
        alias="openai_api_key",
        default_factory=secret_from_env("OPENAI_API_KEY", default=""),
    )
    instructions: str | None = None
    tools: list[BaseTool] | None = None
    url: str = Field(default=DEFAULT_URL)

    async def aconnect(
        self,
        input_stream: AsyncIterator[str],
        send_output_chunk: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Connect to the OpenAI API and send and receive messages.

        input_stream: AsyncIterator[str]
            Stream of input events to send to the model. Usually transports input_audio_buffer.append events from the microphone.
        output: Callable[[str], None]
            Callback to receive output events from the model. Usually sends response.audio.delta events to the speaker.

        """
        # formatted_tools: list[BaseTool] = [
        #     tool if isinstance(tool, BaseTool) else tool_converter.wr(tool)  # type: ignore
        #     for tool in self.tools or []
        # ]
        tools_by_name = {tool.name: tool for tool in self.tools}
        tool_executor = VoiceToolExecutor(tools_by_name=tools_by_name)
        
        

        async with connect(
            model=self.model, api_key=self.api_key.get_secret_value(), url=self.url
        ) as (
            model_send,
            model_receive_stream,
        ):
            # sent tools and instructions with initial chunk
            tool_defs = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {"type": "object", "properties": tool.args},
                }
                for tool in tools_by_name.values()
            ]
            await model_send(
                {
                    "type": "session.update",
                    "session": {
                        "instructions": self.instructions,
                        "input_audio_transcription": {
                            "model": "gpt-4o-transcribe",
                            "language": "tr", 
                            "prompt": "Profesyonel müşteri temsilcisi görüşmelerine ait ses kaydı transkripsiyonu. Lütfen, kullanıcının söylediği ifadeleri olduğu gibi, herhangi bir yorum, özet veya yeniden ifade yapmadan metne dökün. Özellikle, yer adları, Türkiye'deki il/ilçe isimleri gibi özel isimleri orijinal biçimleriyle koruyun. Eğer ses girişi boşsa, sadece sessizlik ya da anlamsız seslerden oluşuyorsa, hiçbir transkripsiyon üretmeyin. Cevabınızı uzatmadan, mantıklı bir cümleyle tamamlayınız.Cevabınız sırasında kullanıcı bir şeyler söylerse, DURMAYIN. Sesli yanıtınızı her zaman tamamlayın.",

                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.6,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500,
                            "create_response": True,
                        },
                        "tools": tool_defs,
                        # "temperature": 0.6,
                    },
                }
            )
            
            
            async for stream_key, data_raw in amerge(
                input_mic=input_stream,
                output_speaker=model_receive_stream,
                tool_outputs=tool_executor.output_iterator(),
            ):
                try:
                    data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
                except json.JSONDecodeError:
                    print("error decoding data:", data_raw)
                    continue

                if stream_key == "input_mic":
                    if data.get("type") == "input_audio_buffer.append" and "audio" in data:
                        audio_bytes = base64.b64decode(data["audio"])
                        
                        if not is_speech(audio_bytes, sample_rate=16000):
                            continue
                    await model_send(data)
                elif stream_key == "tool_outputs":
                    print("tool output", data)
                    await model_send(data)
                    await model_send({"type": "response.create", "response": {}})
                elif stream_key == "output_speaker":
                    t = data["type"]
                    if t == "response.audio.delta" and "delta" in data:
                        audio_bytes = base64.b64decode(data["delta"])
                        
                        await send_output_chunk(json.dumps(data))
                    elif t == "input_audio_buffer.speech_started":
                        print("interrupt")
                        await send_output_chunk(json.dumps(data))
                    elif t == "error":
                        print("error:", data)
                    elif t == "response.function_call_arguments.done":
                        print("tool call", data)
                        await tool_executor.add_tool_call(data)
                    elif t == "response.audio_transcript.done":
                        print("model:", data["transcript"])
                    elif t == "conversation.item.input_audio_transcription.completed":
                        print("user:", data["transcript"])
                    elif t in EVENTS_TO_IGNORE:
                        pass
                    else:
                        print(t)


__all__ = ["OpenAIVoiceReactAgent"]