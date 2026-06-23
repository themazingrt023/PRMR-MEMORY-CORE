import math
import subprocess
import textwrap
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "v056" / "video"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SILENT_MP4 = OUT_DIR / "prmr_founder_demo_v056_silent.mp4"
FINAL_MP4 = OUT_DIR / "prmr_founder_demo_v056.mp4"
NARRATION_TXT = OUT_DIR / "prmr_founder_demo_v056_narration.txt"
NARRATION_WAV = OUT_DIR / "prmr_founder_demo_v056_narration.wav"

WIDTH = 1920
HEIGHT = 1080
FPS = 18


def font(name, size):
    fonts = {
        "serif": r"C:\Windows\Fonts\georgia.ttf",
        "serif_bold": r"C:\Windows\Fonts\georgiab.ttf",
        "sans": r"C:\Windows\Fonts\arial.ttf",
        "sans_bold": r"C:\Windows\Fonts\arialbd.ttf",
        "mono": r"C:\Windows\Fonts\consola.ttf",
    }
    path = fonts.get(name, fonts["sans"])
    if Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


F_SERIF_96 = font("serif", 96)
F_SERIF_74 = font("serif", 74)
F_SERIF_58 = font("serif", 58)
F_SERIF_42 = font("serif", 42)
F_SANS_38 = font("sans", 38)
F_SANS_32 = font("sans", 32)
F_SANS_26 = font("sans", 26)
F_SANS_22 = font("sans", 22)
F_MONO_24 = font("mono", 24)
F_MONO_18 = font("mono", 18)


SCENES = [
    {
        "duration": 7,
        "eyebrow": "AFTERNUM INDUSTRIES",
        "title": "PRMR Memory Core",
        "subtitle": "Continuity infrastructure for AI systems and organisations.",
        "body": "Preserve what changed, what matters, what became stale, and what needs review.",
        "mode": "hero",
    },
    {
        "duration": 8,
        "eyebrow": "THE CONTINUITY GAP",
        "title": "Storage remembers data.\nPRMR remembers change.",
        "body": "Modern systems store logs, chats, vectors, summaries, tickets, documents, and user events. But storage alone does not preserve continuity.",
        "mode": "problem",
    },
    {
        "duration": 8,
        "eyebrow": "PRODUCT TRUTH",
        "title": "Not an AI model.",
        "body": "PRMR sits beside AI systems, databases, vector stores, and SaaS tools as a continuity layer. It preserves a smaller, safer packet before the next action.",
        "mode": "packet",
    },
    {
        "duration": 8,
        "eyebrow": "LOCAL CONTROLLED-ALPHA DEMO",
        "title": "Browser → Proxy → Local Bridge",
        "body": "The demo page calls a Next.js proxy route. The route runs server-side and calls a local PRMR bridge using synthetic fixture data only.",
        "mode": "flow",
    },
    {
        "duration": 8,
        "eyebrow": "CONTINUITY PACKET",
        "title": "Current state. Active signals.\nStale signals. Evidence.",
        "body": "The packet captures the useful shape of change so the system does not need to replay every raw event in the visible interface.",
        "mode": "cards",
    },
    {
        "duration": 8,
        "eyebrow": "PUBLIC-SAFE OUTPUT",
        "title": "Explain without overexposing.",
        "body": "The public-safe explanation avoids private diagnostic detail. The least-harm action stays review-oriented and does not make a final automated decision.",
        "mode": "explain",
    },
    {
        "duration": 8,
        "eyebrow": "ACCESS BOUNDARY",
        "title": "Wrong-key and cross-client paths are denied.",
        "body": "The frontend receives public denial outcomes only. Secret material, vault scope, and private diagnostic traces stay server-side.",
        "mode": "denial",
    },
    {
        "duration": 8,
        "eyebrow": "INTERNAL LOCAL EVIDENCE",
        "title": "Truth gauntlet and sandbox checks: PASS",
        "body": "V0.50, V0.52, V0.52.2, V0.53.1, and V0.55 are passing as internal/local milestones. These are not external certification.",
        "mode": "evidence",
    },
    {
        "duration": 8,
        "eyebrow": "BOUNDARY",
        "title": "Local controlled-alpha evidence.",
        "body": "Synthetic data only. Not hosted production. Not bank approval. Not compliance approval. Not legal approval. Not external security certification. Not real-world validation.",
        "mode": "boundary",
    },
    {
        "duration": 7,
        "eyebrow": "CONTROLLED ALPHA",
        "title": "For teams with messy context\nand continuity problems.",
        "body": "Afternum Industries is opening controlled alpha conversations with AI builders, SaaS teams, and organisations that need better continuity.",
        "mode": "close",
    },
]


NARRATION = """
PRMR Memory Core is continuity infrastructure for AI systems and organisations.
It helps systems preserve what changed, what matters, what became stale, and what needs review.

Modern systems store logs, chats, vectors, summaries, tickets, documents, user events, support history, and transaction-like activity.
But storage alone does not preserve continuity.

PRMR Memory Core is not an AI model.
It sits beside AI systems, databases, vector stores, and SaaS tools as a continuity layer.

In the local controlled-alpha demo, the browser opens the PRMR demo page, selects a synthetic scenario, and clicks Run Local Demo.
The browser calls a Next.js proxy route. The route runs server-side and calls a local PRMR demo bridge.
The bridge uses synthetic fixture data and returns public-safe output.

The frontend renders synthetic events, continuity packet, reconstructed state, public-safe explanation, least-harm action, report preview, and denial path proof.

The continuity packet captures current state, active signals, stale signals, evidence summary, and continuity summary.
The public-safe explanation avoids private diagnostic detail.
The least-harm action stays review-oriented and does not make a final automated decision.

Internal local milestones currently show the whole-core truth gauntlet, local alpha API sandbox, sandbox integrity audit, replay pack, and frontend-to-demo-backend connection passing.
These are internal and local checks, not external certification.

This is local controlled-alpha evidence using synthetic data.
It is not hosted production, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

Afternum Industries is opening controlled alpha conversations with AI builders, SaaS teams, and organisations dealing with messy context and continuity problems.
""".strip()


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, t)))


def lerp(a, b, t):
    return a + (b - a) * t


def draw_text(draw, xy, text, font_obj, fill, spacing=12, anchor=None):
    draw.multiline_text(xy, text, font=font_obj, fill=fill, spacing=spacing, anchor=anchor)


def wrapped(text, width):
    return "\n".join(textwrap.wrap(text, width=width))


def base_frame(global_t):
    img = Image.new("RGB", (WIDTH, HEIGHT), (9, 9, 9))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # soft moving light
    cx = int(WIDTH * (0.42 + 0.12 * math.sin(global_t * 0.18)))
    cy = int(HEIGHT * (0.35 + 0.08 * math.cos(global_t * 0.13)))
    for radius, alpha in [(520, 34), (340, 38), (170, 32)]:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(190, 205, 220, alpha))

    # sparse data rain / vertical traces
    for col in range(0, WIDTH, 92):
        phase = (global_t * 28 + col * 0.17) % HEIGHT
        alpha = int(20 + 18 * math.sin(col * 0.03 + global_t))
        draw.line((col, 0, col, HEIGHT), fill=(180, 190, 200, 8), width=1)
        for k in range(6):
            y = int((phase + k * 84) % HEIGHT)
            glyph = "01xDS<>~"[int((col + k + global_t) % 8)]
            draw.text((col + 8, y), glyph, font=F_MONO_18, fill=(210, 220, 230, max(18, alpha - k * 4)))

    # bottom horizon
    y = int(HEIGHT * 0.76 + math.sin(global_t * 0.7) * 3)
    draw.line((0, y, WIDTH, y), fill=(230, 238, 245, 28), width=1)
    for x in range(0, WIDTH, 180):
        draw.ellipse((x - 60, y - 10, x + 60, y + 10), outline=(230, 238, 245, 20), width=1)

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img


def draw_logo(draw, x, y, scale=1.0, alpha=220):
    r = int(56 * scale)
    draw.ellipse((x - r, y - r, x + r, y + r), outline=(230, 238, 245, alpha), width=max(2, int(3 * scale)))
    draw.polygon([(x, y - r + 12), (x - r + 18, y + r - 12), (x, y + r // 3), (x + r - 18, y + r - 12)], outline=(230, 238, 245, alpha), fill=None)
    draw.line((x, y - r + 12, x, y + r - 12), fill=(230, 238, 245, alpha), width=max(2, int(3 * scale)))
    draw.line((x - r + 22, y + r - 14, x, y + r // 3, x + r - 22, y + r - 14), fill=(230, 238, 245, int(alpha * 0.7)), width=max(1, int(2 * scale)))


def draw_card(draw, box, title, body, alpha=180):
    x1, y1, x2, y2 = box
    draw.rectangle(box, outline=(205, 215, 225, alpha // 2), fill=(14, 14, 14, 155), width=1)
    draw.line((x1, y1, x1 + 54, y1), fill=(230, 238, 245, alpha), width=2)
    draw.line((x1, y1, x1, y1 + 54), fill=(230, 238, 245, alpha), width=2)
    draw.text((x1 + 30, y1 + 28), title, font=F_MONO_18, fill=(210, 220, 230, alpha))
    draw.multiline_text((x1 + 30, y1 + 70), wrapped(body, 35), font=F_SANS_22, fill=(225, 230, 235, int(alpha * 0.75)), spacing=8)


def draw_network(draw, t, left=1040, top=270, w=620, h=390):
    points = []
    for i in range(30):
        px = left + int((math.sin(i * 2.13) * 0.5 + 0.5) * w)
        py = top + int((math.cos(i * 1.71) * 0.5 + 0.5) * h)
        points.append((px, py))
    for i, p in enumerate(points):
        for j in range(i + 1, len(points)):
            q = points[j]
            d = math.hypot(p[0] - q[0], p[1] - q[1])
            if d < 160:
                a = int(max(8, 45 - d * 0.2))
                draw.line((*p, *q), fill=(220, 228, 236, a), width=1)
    for i, p in enumerate(points):
        pulse = 0.5 + 0.5 * math.sin(t * 2 + i)
        r = int(3 + pulse * 3)
        draw.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=(230, 238, 245, int(80 + pulse * 100)))


def draw_scene(scene, local_t, duration, global_t):
    img = base_frame(global_t)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    fade_in = ease(min(local_t / 1.0, 1))
    fade_out = ease(min((duration - local_t) / 0.8, 1))
    a = int(255 * min(fade_in, fade_out))
    slide = int(lerp(22, 0, fade_in))

    # top bar
    draw_logo(draw, 118, 84, 0.38, alpha=int(210 * fade_in))
    draw.text((165, 68), "AFTERNUM", font=F_MONO_24, fill=(245, 247, 250, int(220 * fade_in)))
    draw.text((WIDTH - 420, 76), "LOCAL CONTROLLED-ALPHA DEMO", font=F_MONO_18, fill=(200, 210, 220, int(120 * fade_in)))

    # scene visual motifs
    mode = scene["mode"]
    if mode in {"problem", "denial", "close"}:
        draw_network(draw, global_t)
    if mode in {"packet", "cards", "explain", "evidence"}:
        draw_card(draw, (1060, 250, 1620, 395), "CURRENT STATE", "preserved for the next action", alpha=int(170 * fade_in))
        draw_card(draw, (1110, 430, 1670, 575), "ACTIVE SIGNALS", "what still matters now", alpha=int(145 * fade_in))
        draw_card(draw, (1010, 610, 1570, 755), "STALE SIGNALS", "what should not drive the next step", alpha=int(125 * fade_in))
    if mode == "flow":
        labels = ["BROWSER", "NEXT.JS PROXY", "LOCAL PRMR BRIDGE", "PUBLIC-SAFE JSON"]
        y = 430
        for i, label in enumerate(labels):
            x = 300 + i * 370
            draw.rectangle((x, y, x + 260, y + 92), outline=(230, 238, 245, int(95 * fade_in)), fill=(15, 15, 15, int(150 * fade_in)), width=1)
            draw.text((x + 28, y + 34), label, font=F_MONO_18, fill=(235, 240, 245, int(190 * fade_in)))
            if i < len(labels) - 1:
                draw.line((x + 275, y + 46, x + 352, y + 46), fill=(230, 238, 245, int(110 * fade_in)), width=2)
                draw.polygon([(x + 352, y + 46), (x + 338, y + 38), (x + 338, y + 54)], fill=(230, 238, 245, int(110 * fade_in)))

    if mode == "hero":
        draw_logo(draw, WIDTH // 2, 250, 1.0, alpha=int(220 * fade_in))
        draw.text((WIDTH // 2, 360), "AFTERNUM", font=F_MONO_24, fill=(230, 238, 245, int(190 * fade_in)), anchor="mm")

    # main typography
    text_x = 150
    eyebrow_y = 230 + slide
    title_y = 305 + slide
    body_y = 555 + slide
    if mode == "hero":
        text_x = WIDTH // 2
        eyebrow_y = 470 + slide
        title_y = 535 + slide
        body_y = 705 + slide
        draw.text((text_x, eyebrow_y), scene["eyebrow"], font=F_MONO_18, fill=(205, 215, 225, int(150 * a / 255)), anchor="mm")
        draw.multiline_text((text_x, title_y), scene["title"], font=F_SERIF_96, fill=(248, 248, 248, a), spacing=10, anchor="mm", align="center")
        draw.multiline_text((text_x, body_y), wrapped(scene["body"], 70), font=F_SANS_32, fill=(230, 234, 238, int(190 * a / 255)), spacing=12, anchor="mm", align="center")
    else:
        draw.text((text_x, eyebrow_y), scene["eyebrow"], font=F_MONO_18, fill=(205, 215, 225, int(150 * a / 255)))
        draw.line((text_x, eyebrow_y + 48, WIDTH - 150, eyebrow_y + 48), fill=(230, 238, 245, int(48 * a / 255)), width=1)
        draw.multiline_text((text_x, title_y), scene["title"], font=F_SERIF_74 if len(scene["title"]) < 50 else F_SERIF_58, fill=(248, 248, 248, a), spacing=12)
        draw.multiline_text((text_x, body_y), wrapped(scene["body"], 56), font=F_SANS_32, fill=(230, 234, 238, int(195 * a / 255)), spacing=12)

    # footer boundary
    draw.text((150, HEIGHT - 84), "Synthetic data only · local controlled-alpha evidence · not hosted production", font=F_MONO_18, fill=(220, 228, 236, int(96 * fade_in)))

    img = Image.alpha_composite(img, overlay)
    return np.asarray(img.convert("RGB"))


def render_video():
    total_frames = sum(int(scene["duration"] * FPS) for scene in SCENES)
    print(f"Rendering {total_frames} frames to {SILENT_MP4}")
    writer = imageio.get_writer(
        SILENT_MP4,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=1,
        ffmpeg_log_level="warning",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    frame_index = 0
    try:
        for scene in SCENES:
            frames = int(scene["duration"] * FPS)
            for i in range(frames):
                local_t = i / FPS
                global_t = frame_index / FPS
                writer.append_data(draw_scene(scene, local_t, scene["duration"], global_t))
                frame_index += 1
    finally:
        writer.close()


def write_narration_text():
    NARRATION_TXT.write_text(NARRATION, encoding="utf-8")


def make_narration_wav():
    escaped_wav = str(NARRATION_WAV).replace("'", "''")
    escaped_txt = str(NARRATION_TXT).replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$text = Get-Content -Raw -Path '{escaped_txt}'
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = -1
$synth.Volume = 92
$synth.SetOutputToWaveFile('{escaped_wav}')
$synth.Speak($text)
$synth.Dispose()
"""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    return result.returncode == 0 and NARRATION_WAV.exists()


def mux_audio_if_available():
    if not NARRATION_WAV.exists():
        SILENT_MP4.replace(FINAL_MP4)
        return False
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(SILENT_MP4),
        "-i",
        str(NARRATION_WAV),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(FINAL_MP4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        SILENT_MP4.replace(FINAL_MP4)
        return False
    return True


def main():
    write_narration_text()
    render_video()
    audio_ok = make_narration_wav()
    mux_ok = mux_audio_if_available()
    print("Created:", FINAL_MP4)
    print("Narration WAV:", "yes" if audio_ok else "no")
    print("Audio muxed:", "yes" if mux_ok else "no")
    print("Narration text:", NARRATION_TXT)


if __name__ == "__main__":
    main()
