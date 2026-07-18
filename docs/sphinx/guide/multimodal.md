# Multimodal Input

Multimodal messages use `ContentPart` lists:

```python
from praval import Agent, ContentPart

agent = Agent("vision", provider="openai", model="gpt-5.4-mini")
response = agent.generate(
    [
        ContentPart.text_part("Describe this image."),
        ContentPart.image_url("https://example.com/image.png"),
    ]
)
```

For direct runtime calls:

```python
from praval import ContentPart, ModelMessage, ModelRequest

request = ModelRequest(
    provider="gemini",
    model="gemini-3.5-flash",
    messages=[
        ModelMessage(
            role="user",
            content=[
                ContentPart.text_part("What is shown?"),
                ContentPart.image_base64("...", "image/png"),
            ],
        )
    ],
)
```

Supported part constructors:

| Constructor | Meaning |
| --- | --- |
| `ContentPart.text_part(text)` | Text input. |
| `ContentPart.image_url(url)` | Remote image URL. |
| `ContentPart.image_base64(data, mime_type)` | Inline base64 image. |
| `ContentPart.file_data(data, mime_type)` | Inline file data. |
| `ContentPart.file_url(url, mime_type)` | Remote file reference. |
| `ContentPart.audio_base64(data, mime_type)` | Inline base64 audio. |
| `ContentPart.audio_url(url, mime_type)` | Remote audio reference. |
| `ContentPart.video_base64(data, mime_type)` | Inline base64 video. |
| `ContentPart.video_url(url, mime_type)` | Remote video reference. |

The runtime validates content parts against the resolved capability profile.
Unsupported image, file, audio, and unknown parts fail before the adapter is
called. This is deliberate: a profile must be truthful or explicitly overridden.

Gemini accepts image, file, audio, and video parts in the 0.8 adapter. A
`file_url` must already be a URI accepted by the Gemini API, such as a Gemini
Files API URI or a provider-supported remote object URI. Praval does not upload
local files to Gemini in this release. Encode small local inputs as base64 or
upload them separately and pass the resulting reference.

OpenAI generation supports image input in the stable 0.8 profile. File,
audio, and video generation inputs remain disabled until the corresponding
adapter paths are implemented and tested. Anthropic supports image input;
other document or PDF forms are not advertised by the current adapter.

## Request-Based Voice

OpenAI agents can transcribe an audio file, use the transcript in a normal
agent turn, and synthesize the reply:

```python
from pathlib import Path

from praval import Agent

agent = Agent("voice-assistant", provider="openai", model="gpt-5.4-mini")

transcript = agent.transcribe(
    Path("question.wav"),
    model="gpt-4o-transcribe",
    language="en",
)
reply = agent.chat(transcript)
audio = agent.speak(
    reply,
    model="tts-1",
    voice="alloy",
    response_format="mp3",
)
Path("reply.mp3").write_bytes(audio)
```

`Agent.transcribe()` accepts bytes, a local path, a binary file object, or an
OpenAI SDK file tuple. It returns transcription text. `Agent.speak()` returns
audio bytes. These helpers do not add audio operations to conversation history;
only the explicit `chat()` call adds a turn.

The default audio models are separate from the agent's chat model:
`gpt-4o-transcribe` for transcription and `tts-1` for speech. Override them per
call, or set `transcription_model` and `speech_model` in the agent's
`provider_options` configuration.

This is a request-response API. In Praval, a realtime session would keep a
provider connection open for continuous input/output events and potentially
bidirectional audio over WebRTC or WebSocket. Those persistent sessions,
streaming audio conversations, and raw binary Spore transport are deferred
beyond the 0.8 line.
`ContentPart.audio_*` and `ContentPart.video_*` are generation inputs for
capable providers such as Gemini; they are distinct from the transcription and
speech helpers.

## Multimodal Spores

`Spore` can carry JSON-safe `content_parts`, `knowledge_references`, and
`data_references` alongside the compatibility `knowledge`/`payload` fields:

```python
from datetime import datetime, timezone

from praval import ContentPart, Spore, SporeType

spore = Spore(
    id="analysis-1",
    spore_type=SporeType.KNOWLEDGE,
    from_agent="vision",
    to_agent="reviewer",
    knowledge={"summary": "Inspect the source image"},
    created_at=datetime.now(timezone.utc),
    content_parts=[
        ContentPart.image_url("https://example.com/source.png")
    ],
    data_references=["s3_main://object/images/source.png"],
)
```

Rich Spores use a versioned JSON AMQP envelope. Knowledge-only Spores retain
the legacy AMQP body for compatibility. Raw bytes are rejected: use base64
content parts for small data and storage references for large data.
