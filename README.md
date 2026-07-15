# OpenWebUI Veo 3.1 Video Generator

Generate hyper-realistic, cinematic videos directly within [OpenWebUI](https://openwebui.com/) using Google's **Veo 3.1** model!

This script fully integrates Veo 3.1's advanced long-running operations and dynamically embeds a native HTML5 video player into your chat stream.

> **Note:** This tool runs on Google's **Gemini Enterprise Agent Platform** (formerly Vertex AI). The 2026 rebrand changed the Cloud Console product name and some IAM role labels, but the API endpoint (`aiplatform.googleapis.com`), model IDs, and SDKs are unchanged — so the setup below works as-is.

![OpenWebUI Veo 3.1 Settings](https://github.com/spawnofsociety2/openwebui-veo-video/raw/master/assets/openwebui_veo31_videogen.jpg)

### Features

✨ **Native Chat Embeds**: Videos render flawlessly inline as native HTML5 video players.
✨ **Image-to-Video**: Upload reference images directly in the chat to use as starting frames or style references!
✨ **Video Editing**: Edit existing videos by uploading them or providing a GCS URI (`gs://`).
✨ **Custom UserValves**: Includes a custom settings UI allowing each user to choose their own **Aspect Ratio** (16:9 or 9:16), **Duration** (4s, 6s, 8s), and **Resolution** (720p, 1080p, 4K)!
✨ **Multi-Video Support**: Set the tool to generate up to 4 videos at once, and they will all stack neatly in the chat interface!
✨ **Downloads**: Direct download links are automatically generated below each video.
✨ **Non-blocking**: Uses an async polling loop to fetch long-running 4K video generation tasks without freezing your chat interface.

### Prerequisites & Authentication

You must have a Google Cloud Project with the **Gemini Enterprise Agent Platform (formerly Vertex AI) API** enabled. Unlike OpenAI, Google requires proper IAM Authentication rather than a simple API key. Here is how to set it up depending on how you installed OpenWebUI:

#### Option 1: You installed via Python (`pip` / `uv`)

1. Install the Google Cloud SDK (`gcloud` CLI) on your host machine.
2. Open your terminal/command prompt and run: `gcloud auth application-default login`
3. A browser window will open. Log into your Google Cloud account.
4. Restart your OpenWebUI Python server. The script will automatically detect the credentials!

#### Option 2: You installed via Docker

Since OpenWebUI runs inside an isolated container, that container needs to be handed your Google Cloud credentials.

1. Go to your Google Cloud Console and navigate to **IAM & Admin > Service Accounts**.
2. Create a new Service Account and grant it the `Vertex AI User` role. *(The console may show this under a renamed label after the 2026 rebrand — the underlying permission is the same.)*
3. Click on the Service Account, go to the **Keys** tab, and select **Add Key > Create New Key > JSON**. This will download a `.json` file.
4. Move this JSON file into your OpenWebUI data directory on your host (for example, name it `gcp-key.json`).
5. Update your OpenWebUI `docker run` command (or `docker-compose.yml`) to add this environment variable:
`-e GOOGLE_APPLICATION_CREDENTIALS="/app/backend/data/gcp-key.json"` *(Note: Adjust the container path based on where your OpenWebUI data volume is mounted).*

#### Option 3: You installed via Kubernetes (Helm)

1. Download your Service Account JSON key from Google Cloud (same as Docker steps 1-3).
2. Create a secret in your OpenWebUI namespace:
`kubectl create secret generic vertex-auth --from-file=gcp-key.json=./gcp-key.json`
3. Update your OpenWebUI Helm `values.yaml` to mount this secret:

```yaml
extraEnvVars:
  - name: GOOGLE_APPLICATION_CREDENTIALS
    value: "/auth/gcp-key.json"
extraVolumes:
  - name: vertex-auth-volume
    secret:
      secretName: vertex-auth
extraVolumeMounts:
  - name: vertex-auth-volume
    mountPath: "/auth"
    readOnly: true
```

### Setup Instructions

1. Install this tool in your workspace using the `veo_video_tool.py` script.
2. Click the **Valves** (gear) icon for this tool on the admin page.
3. Enter your Google Cloud **Project ID**.
4. Enter your **Location ID** (e.g., `us-central1`).
5. (Optional) Adjust the `Max Timeout Seconds` if you plan to generate 4K 8-second videos, as those can take several minutes.

### Usage

Users can click the Tool Settings gear icon in their chat interface to customize their preferred aspect ratio, resolution, duration, and the number of videos to generate. Then, just mention the tool in chat with your prompt!

#### Using Image & Video References

You can provide existing media for Veo 3.1 to use as a starting frame or reference:

- **Direct Upload (Images & Short videos)**: Click the `+` attachment icon in OpenWebUI to attach an image or short video directly to your chat message.
- **Image URLs**: Paste a public URL to an image in your prompt, and the tool will download it automatically.
- **GCS URI (Long/Large videos)**: For larger videos, upload the video to a Google Cloud Storage bucket and provide the `gs://your-bucket-name/video.mp4` link in your chat prompt. The tool will seamlessly hand it off to the platform!

### 💡 Veo 3.1 Prompting Guide

For official tips, tricks, and best practices on prompting Veo 3.1 to get the best possible videos, check out the [Official Gemini API Veo Prompting Guide](https://ai.google.dev/gemini-api/docs/veo#prompt-guide).
