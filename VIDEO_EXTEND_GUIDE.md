# Video Extension Feature - Usage Guide

## Overview

Flow2API now supports video extension (continuation) using Veo 3.1 Extend models. This allows you to take an existing generated video and extend it further by continuing the motion from the last frames.

## How It Works

1. **Generate Initial Video**: Create a video using any standard model (T2V, R2V, I2V)
2. **Get Media ID**: The response now includes a `mediaGenerationId`
3. **Extend Video**: Use the extend model with the media ID to continue the video

## Models Available

### Portrait (9:16)
- `veo_3_1_extend_fast_portrait` - Standard tier
- `veo_3_1_extend_fast_portrait_ultra` - Ultra tier (TIER_TWO accounts)

### Landscape (16:9)
- `veo_3_1_extend_fast_landscape` - Standard tier
- `veo_3_1_extend_fast_landscape_ultra` - Ultra tier (TIER_TWO accounts)

## API Usage

### Step 1: Generate Initial Video

```bash
curl -X POST http://localhost:18282/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo_3_1_r2v_fast_portrait_ultra",
    "messages": [{
      "role": "user",
      "content": "Catholic priest speaking about faith"
    }],
    "stream": false
  }'
```

### Response Format

```json
{
  "id": "chatcmpl-1769799827",
  "object": "chat.completion",
  "created": 1769799827,
  "model": "flow2api",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "```html\n<video src='https://...' controls></video>\n```\n\n**Media ID:** `CAUSJGE0NWU...`\n\n_Use this ID for video extension with extend models_"
    },
    "finish_reason": "stop"
  }],
  "media_id": "CAUSJGE0NWUyZTFlLWRjNzUtNDVkOS1hZDFmLWIyMGVmM2ViNGI4MxokMDdhYjExODYtYzIzMC00NDA2LThkNDgtNjE3YTkxYTBkNjY0IgNDQUUqJDk5MDNiZWJlLTY5ZDEtNDVkZi04MWYwLTYzYmQ4YWYzNDc1Yg"
}
```

**Key Fields:**
- `choices[0].message.content` - Contains video URL and Media ID
- `media_id` - Top-level field for easy access

### Step 2: Extend the Video

Use the media ID from step 1 with frame indices to specify which frames to extend from.

```bash
curl -X POST http://localhost:18282/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo_3_1_extend_fast_portrait_ultra",
    "messages": [{
      "role": "user",
      "content": "continue what he was speaking [video_id:CAUSJGE0NWU...,start_frame:168,end_frame:191]"
    }],
    "stream": false
  }'
```

**Prompt Format:**
```
<continuation_prompt> [video_id:<MEDIA_ID>,start_frame:<N>,end_frame:<M>]
```

**Parameters:**
- `video_id` - Media ID from the original video
- `start_frame` - Frame index to start extending from (typically last 24 frames)
- `end_frame` - Frame index to end at (typically last frame, which is 191 for 8-second videos)

**Frame Calculation:**
- Veo 3.1 videos are ~8 seconds at 24 FPS = 192 frames (0-191)
- To extend from last second: `start_frame:168,end_frame:191` (last 24 frames)

### Step 3: Chain Multiple Extensions

You can continue extending indefinitely:

```bash
# Extend 1 → 2
curl ... -d '{"model": "veo_3_1_extend_fast_portrait_ultra", ...}'
# Get new media_id from response

# Extend 2 → 3
curl ... -d '{"model": "veo_3_1_extend_fast_portrait_ultra", "messages": [{"content": "continue [video_id:NEW_MEDIA_ID,start_frame:168,end_frame:191]"}]}'
```

## Python Example

```python
import requests

API_URL = "http://localhost:18282/v1/chat/completions"
API_KEY = "YOUR_API_KEY"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Step 1: Generate initial video
response1 = requests.post(API_URL, headers=headers, json={
    "model": "veo_3_1_r2v_fast_portrait_ultra",
    "messages": [{"role": "user", "content": "Catholic priest speaking"}],
    "stream": False
})

result1 = response1.json()
media_id = result1["media_id"]
print(f"Generated video with media_id: {media_id}")

# Step 2: Extend the video
response2 = requests.post(API_URL, headers=headers, json={
    "model": "veo_3_1_extend_fast_portrait_ultra",
    "messages": [{
        "role": "user",
        "content": f"continue speaking [video_id:{media_id},start_frame:168,end_frame:191]"
    }],
    "stream": False
})

result2 = response2.json()
extended_media_id = result2["media_id"]
print(f"Extended video with new media_id: {extended_media_id}")
```

## Tips

1. **Frame Selection**: Use the last 1-2 seconds of frames for smooth continuation
2. **Prompt Consistency**: Use similar prompts for seamless extensions
3. **Chain Carefully**: Each extension adds ~8 seconds
4. **Media ID Storage**: Save media IDs if you want to branch or retry extensions

## Technical Details

### API Endpoint
- Uses Google's VideoFX API: `https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoExtendVideo`

### Model Keys (Internal)
- `veo_3_1_extend_fast_portrait`
- `veo_3_1_extend_fast_portrait_ultra`
- `veo_3_1_extend_fast_landscape`
- `veo_3_1_extend_fast_landscape_ultra`

### Response Structure
All video and image generation responses now include:
- **Stream mode**: Media ID in HTML comment `<!-- media_id:... -->`
- **Non-stream mode**:
  - `media_id` field at response root
  - Media ID displayed in message content with usage instructions

## Troubleshooting

**Error: "Extend模型需要提供 video_id, start_frame, end_frame 参数"**
- Make sure your prompt includes all three parameters in the correct format

**Error: "不支持的模型" (Unsupported model)**
- Check that you're using an extend model (`veo_3_1_extend_fast_*`)

**Video doesn't continue smoothly**
- Adjust frame indices to use more frames (e.g., `start_frame:144` instead of 168)
- Ensure prompt describes continuation of the same action

## Example Response

```json
{
  "id": "chatcmpl-1769799827",
  "object": "chat.completion",
  "created": 1769799827,
  "model": "flow2api",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "```html\n<video src='https://storage.googleapis.com/...' controls></video>\n```\n\n**Media ID:** `CAUSJGE0NWUyZTFlLWRjNzUtNDVkOS1hZDFmLWIyMGVmM2ViNGI4MxokMDdhYjExODYtYzIzMC00NDA2LThkNDgtNjE3YTkxYTBkNjY0IgNDQUUqJDk5MDNiZWJlLTY5ZDEtNDVkZi04MWYwLTYzYmQ4YWYzNDc1Yg`\n\n_Use this ID for video extension with extend models_"
    },
    "finish_reason": "stop"
  }],
  "media_id": "CAUSJGE0NWUyZTFlLWRjNzUtNDVkOS1hZDFmLWIyMGVmM2ViNGI4MxokMDdhYjExODYtYzIzMC00NDA2LThkNDgtNjE3YTkxYTBkNjY0IgNDQUUqJDk5MDNiZWJlLTY5ZDEtNDVkZi04MWYwLTYzYmQ4YWYzNDc1Yg"
}
```

---

**Status:** ✅ Production Ready
**Version:** Flow2API v1.0+
**Last Updated:** 2026-01-30
