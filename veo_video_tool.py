"""
title: Veo 3.1 Video Generator
description: Generates high-quality videos using Google Vertex AI's new Veo 3.1 model.
author: Antigravity
version: 1.0
requirements: google-genai, google-auth, google-cloud-storage
"""

import os
import uuid
import base64
import asyncio
import time
from typing import Optional, Callable, Awaitable, Literal
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        PROJECT_ID: str = Field(
            default="your-google-cloud-project-id", 
            description="Google Cloud Project ID"
        )
        LOCATION_ID: str = Field(
            default="us-central1", 
            description="Vertex AI Location for Veo models"
        )
        POLL_INTERVAL_SECONDS: int = Field(
            default=15,
            description="How often to check for video completion"
        )
        MAX_TIMEOUT_SECONDS: int = Field(
            default=900,
            description="Maximum time to wait before failing (in seconds) - high quality video can take a while!"
        )

    class UserValves(BaseModel):
        ASPECT_RATIO: Literal["16:9", "9:16"] = Field(
            default="16:9", description="Aspect ratio of the video."
        )
        DURATION_SECONDS: Literal["4", "6", "8"] = Field(
            default="8", description="Length of the generated video (seconds)."
        )
        RESOLUTION: Literal["720p", "1080p", "4K"] = Field(
            default="720p", description="Output resolution."
        )
        NUMBER_OF_VIDEOS: int = Field(
            default=1, description="Number of results to generate (1-4)."
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()

    async def generate_video(
        self,
        prompt: str,
        reference_image_url: Optional[str] = Field(
            default=None, 
            description="Optional URL of a reference image to use for generating the video. Use this if the user provides an image link."
        ),
        reference_video_url: Optional[str] = Field(
            default=None,
            description="Optional URL of a reference video to edit. Use this if the user provides a video link (e.g. gs:// bucket link or public URL)."
        ),
        __messages__: list = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
        __user__: dict = {}
    ) -> str:
        """
        Generates a video based on the user's prompt using Veo 3.1.
        
        :param prompt: A detailed description of the video you want the model to generate.
        :return: An HTML5 video player containing the generated video(s), or an error message.
        """
        try:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Authenticating with Google Cloud...", "done": False}
                })

            import google.auth
            from google import genai
            from google.genai import types

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

            client = genai.Client(
                vertexai=True,
                project=self.valves.PROJECT_ID,
                location=self.valves.LOCATION_ID,
                credentials=credentials,
            )

            # We'll collect the media parts dynamically
            img_bytes = None
            img_mime_type = None
            vid_bytes = None
            vid_mime_type = None
            vid_gcs_uri = None

            # 1. Check for reference image URL provided by the LLM
            if reference_image_url:
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "Downloading reference image from URL...", "done": False}
                    })
                try:
                    import urllib.request
                    req = urllib.request.Request(reference_image_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        img_bytes = response.read()
                        img_mime_type = response.headers.get_content_type()
                except Exception as e:
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {"description": f"Warning: Failed to fetch reference image URL: {e}", "done": False}
                        })

            # 2. Check for reference video URL provided by the LLM
            if reference_video_url:
                if reference_video_url.startswith("gs://"):
                    vid_gcs_uri = reference_video_url
                else:
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {"description": "Downloading reference video from URL (may take a while)...", "done": False}
                        })
                    try:
                        import urllib.request
                        req = urllib.request.Request(reference_video_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req) as response:
                            vid_bytes = response.read()
                            vid_mime_type = response.headers.get_content_type()
                    except Exception as e:
                        if __event_emitter__:
                            await __event_emitter__({
                                "type": "status",
                                "data": {"description": f"Warning: Failed to fetch reference video URL: {e}", "done": False}
                            })

            # 3. Check for uploaded image/video attachments in the user's last message (Open WebUI standard)
            if __messages__:
                last_msg = __messages__[-1]
                if isinstance(last_msg, dict) and last_msg.get('role') == 'user':
                    images = last_msg.get('images', [])
                    if images:
                        if __event_emitter__:
                            await __event_emitter__({
                                "type": "status",
                                "data": {"description": f"Processing {len(images)} attached media file(s)...", "done": False}
                            })
                        for attachment_uri in images:
                            if isinstance(attachment_uri, str):
                                if attachment_uri.startswith('data:image'):
                                    try:
                                        header, encoded = attachment_uri.split(',', 1)
                                        img_mime_type = header.split(';')[0].split(':')[1]
                                        img_bytes = base64.b64decode(encoded)
                                    except Exception as e:
                                        pass
                                elif attachment_uri.startswith('data:video'):
                                    try:
                                        header, encoded = attachment_uri.split(',', 1)
                                        vid_mime_type = header.split(';')[0].split(':')[1]
                                        vid_bytes = base64.b64decode(encoded)
                                    except Exception as e:
                                        pass

            # Ensure number of videos is within bounds based on the Vertex AI screenshot (1-4 usually)
            num_videos = max(1, min(4, self.user_valves.NUMBER_OF_VIDEOS))
            duration = int(self.user_valves.DURATION_SECONDS)

            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": f"Initializing Veo 3.1 generation request ({self.user_valves.RESOLUTION}, {duration}s)...", "done": False}
                })

            def _start_generation():
                source_kwargs = {"prompt": prompt}
                
                # Attach Image if available
                if img_bytes:
                    source_kwargs["image"] = types.Image(image_bytes=img_bytes, mime_type=img_mime_type)
                
                # Attach Video if available
                if vid_bytes:
                    source_kwargs["video"] = types.Video(video_bytes=vid_bytes, mime_type=vid_mime_type)
                elif vid_gcs_uri:
                    source_kwargs["video"] = types.Video(video_uri=vid_gcs_uri, mime_type="video/mp4")

                source = types.GenerateVideosSource(**source_kwargs)
                config = types.GenerateVideosConfig(
                    aspect_ratio=self.user_valves.ASPECT_RATIO,
                    number_of_videos=num_videos,
                    duration_seconds=duration,
                    person_generation="allow_all",
                    generate_audio=True,
                    resolution=self.user_valves.RESOLUTION,
                    # Optional: seed=0 if you want it deterministic, but usually omitted for variations
                )
                return client.models.generate_videos(
                    model="veo-3.1-generate-001", source=source, config=config
                )
                
            operation = await asyncio.to_thread(_start_generation)

            start_time = time.time()
            
            while True:
                if operation.done:
                    break
                    
                elapsed_time = int(time.time() - start_time)
                if elapsed_time > self.valves.MAX_TIMEOUT_SECONDS:
                    raise TimeoutError(f"Video generation timed out after {self.valves.MAX_TIMEOUT_SECONDS} seconds.")
                
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": f"Generating video... (Elapsed time: {elapsed_time}s). Veo 3.1 can take several minutes.", "done": False}
                    })
                
                await asyncio.sleep(self.valves.POLL_INTERVAL_SECONDS)
                
                def _get_operation():
                    # The google-genai SDK handles operation polling nicely
                    return client.operations.get(operation)
                    
                operation = await asyncio.to_thread(_get_operation)

            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Video generated! Processing payload...", "done": False}
                })

            response = operation.result
            
            if not response or not hasattr(response, 'generated_videos') or not response.generated_videos:
                return "The model completed the request but no videos were returned."
                
            generated_videos = response.generated_videos
            video_urls = []
            
            from open_webui.config import STATIC_DIR
            static_videos_dir = os.path.join(STATIC_DIR, "videos")
            os.makedirs(static_videos_dir, exist_ok=True)
                
            for idx, generated_video in enumerate(generated_videos):
                video_data = generated_video.video
                video_bytes = None
                
                if hasattr(video_data, 'video_bytes'):
                    if isinstance(video_data.video_bytes, bytes):
                        video_bytes = video_data.video_bytes
                    elif isinstance(video_data.video_bytes, str):
                        video_bytes = base64.b64decode(video_data.video_bytes)
                
                if not video_bytes and hasattr(video_data, 'b64_data') and video_data.b64_data:
                    video_bytes = base64.b64decode(video_data.b64_data)
                         
                if video_bytes:
                    video_id = str(uuid.uuid4())
                    file_path = os.path.join(static_videos_dir, f"{video_id}.mp4")
                    with open(file_path, "wb") as f:
                        f.write(video_bytes)
                    video_urls.append(f"/static/videos/{video_id}.mp4")
            
            if not video_urls:
                 return "The model completed the request but no valid video data could be extracted from the payload."

            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Videos successfully loaded!", "done": True}
                })

            from fastapi.responses import HTMLResponse
            
            # CSS Aspect ratio formatting: "16:9" -> "16/9"
            css_aspect = self.user_valves.ASPECT_RATIO.replace(":", "/")
            
            video_elements = ""
            for url in video_urls:
                video_elements += f'''
                <div style="margin-bottom:1.5rem;">
                  <video controls autoplay loop style="width:100%;aspect-ratio:{css_aspect};background:#000;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.3);">
                    <source src="{url}" type="video/mp4">
                    Your browser does not support the video tag.
                  </video>
                  <a href="{url}" target="_blank" style="display:block;margin-top:8px;font-family:sans-serif;font-size:0.9em;color:#888;text-align:center;text-decoration:none;">↓ Download Video</a>
                </div>
                '''

            video_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
              body, html {{ margin: 0; padding: 0; overflow: hidden; background: transparent; }}
            </style>
            </head>
            <body>
            <div style="width:100%;max-width:1000px;margin:0 auto;margin-bottom:1rem;">
              {video_elements}
            </div>
            <script>
              function reportHeight() {{
                const h = document.documentElement.scrollHeight;
                parent.postMessage({{ type: 'iframe:height', height: h }}, '*');
              }}
              window.addEventListener('load', reportHeight);
              new ResizeObserver(reportHeight).observe(document.body);
            </script>
            </body>
            </html>
            """.strip()

            plural = "s" if len(video_urls) > 1 else ""
            return (
                HTMLResponse(
                    content=video_html,
                    media_type="text/html",
                    headers={"content-disposition": "inline"}
                ),
                f"Generated {len(video_urls)} video{plural} and natively embedded in the chat! Tell the user to enjoy."
            )

        except Exception as e:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": f"Error: {str(e)}", "done": True}
                })
            return f"Failed to generate video: {str(e)}"
