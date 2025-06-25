from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import tempfile
import os
import base64
import shutil
import whisper
import yt_dlp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import moviepy.config as mpy_config
import webvtt

# Configure ImageMagick path
mpy_config.IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"

model = whisper.load_model("base")

def download_youtube_video_and_subs(url, video_path, subs_path):
    ydl_opts = {
        'outtmpl': video_path,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'hi', 'en-US', 'hi-IN'],  # try English and Hindi subs
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'noplaylist': True,
        'subtitlesformat': 'vtt',
        'skip_download': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Find subtitle file path
        subs_files = [f for f in os.listdir(os.path.dirname(video_path)) if f.endswith('.vtt')]
        if subs_files:
            shutil.move(os.path.join(os.path.dirname(video_path), subs_files[0]), subs_path)
        else:
            # No subs found, leave subs_path empty
            open(subs_path, 'w').close()

def parse_subtitles(subs_path, prompt):
    keywords = prompt.lower().split()
    filtered = []
    try:
        for caption in webvtt.read(subs_path):
            text_lower = caption.text.lower()
            if any(k in text_lower for k in keywords):
                filtered.append({
                    "start": float(caption.start_in_seconds),
                    "end": float(caption.end_in_seconds),
                    "text": caption.text.strip()
                })
            if len(filtered) >= 3:
                break
    except Exception:
        pass
    return filtered

def transcribe_with_whisper(video_path, prompt):
    result = model.transcribe(video_path)
    segments = result.get("segments", [])
    keywords = prompt.lower().split()
    filtered = []
    for seg in segments:
        text_lower = seg['text'].lower()
        if any(k in text_lower for k in keywords):
            filtered.append({
                "start": seg['start'],
                "end": seg['end'],
                "text": seg['text'].strip()
            })
        if len(filtered) >= 3:
            break
    if not filtered:
        filtered = [{
            "start": s['start'],
            "end": s['end'],
            "text": s['text'].strip()
        } for s in segments[:3]]
    return filtered

def make_captioned_gif(video_path, segment, output_path):
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
    video.write_gif(output_path, program='ffmpeg', fps=10)
    clip.close()
    txt_clip.close()
    video.close()

class GenerateGIFAPIView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt", "").strip()
        youtube_url = request.data.get("youtube_url", "").strip()
        video_file = request.FILES.get("video_file", None)

        if not prompt:
            return Response({"error": "Prompt is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not youtube_url and not video_file:
            return Response({"error": "Provide either youtube_url or video_file."}, status=status.HTTP_400_BAD_REQUEST)

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "input_video.mp4")
            subs_path = os.path.join(tmpdir, "subs.vtt")

            try:
                if youtube_url:
                    download_youtube_video_and_subs(youtube_url, video_path, subs_path)
                else:
                    with open(video_path, "wb") as f:
                        for chunk in video_file.chunks():
                            f.write(chunk)
                    open(subs_path, 'w').close()  # no subs for upload

                segments = parse_subtitles(subs_path, prompt)
                if not segments:
                    segments = transcribe_with_whisper(video_path, prompt)

                gifs = []
                for idx, seg in enumerate(segments):
                    gif_path = os.path.join(tmpdir, f"clip_{idx}.gif")
                    make_captioned_gif(video_path, seg, gif_path)
                    with open(gif_path, "rb") as gf:
                        gif_b64 = base64.b64encode(gf.read()).decode('utf-8')
                    gifs.append({
                        "segment_text": seg['text'],
                        "gif_base64": gif_b64,
                    })

                return Response({
                    "message": "GIFs generated successfully.",
                    "gifs": gifs
                })

            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({"error": "Unexpected error: " + str(e)}, status=500)
