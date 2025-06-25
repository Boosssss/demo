from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import tempfile
import os
import re
import base64
import whisper
import yt_dlp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import moviepy.config as mpy_config

# ✅ Correct path to ImageMagick binary
mpy_config.IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"

# Load Whisper model once
print("🔄 Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Whisper model loaded.")

def download_youtube_video(url, output_path):
    try:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("✅ YouTube video downloaded with yt-dlp.")
    except Exception as e:
        raise ValueError(f"yt-dlp failed to download: {str(e)}")

def extract_captions_and_timestamps(video_path, prompt):
    result = model.transcribe(video_path)
    segments = result.get("segments", [])
    keywords = re.findall(r'\w+', prompt.lower())

    filtered_segments = []
    for seg in segments:
        text_lower = seg['text'].lower()
        if any(k in text_lower for k in keywords):
            filtered_segments.append({
                "start": seg['start'],
                "end": seg['end'],
                "text": seg['text'].strip()
            })
        if len(filtered_segments) >= 3:
            break

    if not filtered_segments:
        filtered_segments = [{
            "start": s['start'],
            "end": s['end'],
            "text": s['text'].strip()
        } for s in segments[:3]]

    print("✅ Captions extracted:", filtered_segments)
    return filtered_segments

def make_captioned_gif(video_path, segment, output_path):
    print("🧪 ImageMagick binary path being used:", mpy_config.IMAGEMAGICK_BINARY)
    clip = VideoFileClip(video_path).subclip(segment['start'], segment['end'])

    txt_clip = TextClip(
        segment['text'],
        fontsize=24,
        color='white',
        stroke_color='black',
        stroke_width=2,
        method='caption',
        font='Arial',
        size=(clip.w * 0.8, None)
    ).set_pos(('center', 'bottom')).set_duration(clip.duration)

    video = CompositeVideoClip([clip, txt_clip])
    video.write_gif(output_path, program='ffmpeg')

    # Release resources
    clip.close()
    txt_clip.close()
    video.close()

    print(f"✅ GIF saved to {output_path}")

class GenerateGIFAPIView(APIView):
    def post(self, request):
        print("🚀 POST /api/generate_gif called")

        prompt = request.data.get("prompt", "").strip()
        youtube_url = request.data.get("youtube_url", "").strip()
        video_file = request.FILES.get("video_file", None)

        print("📝 Prompt:", prompt)
        print("🔗 YouTube URL:", youtube_url)
        print("📁 Uploaded file:", video_file.name if video_file else "None")

        if not prompt:
            return Response({"error": "Prompt is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not youtube_url and not video_file:
            return Response({"error": "Provide either youtube_url or video_file."}, status=status.HTTP_400_BAD_REQUEST)

        with tempfile.TemporaryDirectory() as tmpdir:
            print("📂 Temp directory:", tmpdir)
            video_path = os.path.join(tmpdir, "input_video.mp4")

            try:
                if youtube_url:
                    print("⬇️ Downloading YouTube video...")
                    download_youtube_video(youtube_url, video_path)
                else:
                    print("💾 Saving uploaded video...")
                    with open(video_path, "wb") as f:
                        for chunk in video_file.chunks():
                            f.write(chunk)
                    print("✅ Uploaded video saved.")

                print("🧠 Running Whisper transcription...")
                segments = extract_captions_and_timestamps(video_path, prompt)

                gifs = []
                for idx, seg in enumerate(segments):
                    gif_path = os.path.join(tmpdir, f"clip_{idx}.gif")
                    print(f"🎬 Creating GIF #{idx}...")
                    make_captioned_gif(video_path, seg, gif_path)

                    with open(gif_path, "rb") as gf:
                        gif_bytes = gf.read()
                        gif_b64 = base64.b64encode(gif_bytes).decode('utf-8')

                    gifs.append({
                        "segment_text": seg['text'],
                        "gif_base64": gif_b64,
                    })

                print("✅ All GIFs created.")
                return Response({
                    "message": "GIFs generated successfully.",
                    "gifs": gifs
                })

            except Exception as e:
                print("🔥 ERROR:", str(e))
                import traceback
                traceback.print_exc()
                return Response({"error": "Unexpected error: " + str(e)}, status=500)
