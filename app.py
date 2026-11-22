
import io
import sys
import requests
import streamlit as st
import imageio_ffmpeg
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path
import subprocess
import tempfile
import textwrap


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Content Studio",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --------------------------------------------------
# CUSTOM UI DESIGN
# --------------------------------------------------

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #080D1B, #111A32);
        color: #FFFFFF;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    h1, h2, h3 {
        color: #FFFFFF !important;
    }

    .hero {
        padding: 30px;
        border-radius: 20px;
        background: linear-gradient(120deg, #172A52, #39265F);
        border: 1px solid #354878;
        margin-bottom: 25px;
    }

    .hero-title {
        font-size: 38px;
        font-weight: 800;
        color: #FFFFFF;
    }

    .hero-subtitle {
        color: #C7D2FE;
        font-size: 16px;
    }

    .stButton > button {
        background: linear-gradient(90deg, #7657F6, #A855F7);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 20px;
        font-weight: 700;
        width: 100%;
    }

    .stButton > button:hover {
        border: 1px solid #FFD447;
        color: white;
    }

    .stTextInput input, .stTextArea textarea {
        background-color: #17233E;
        color: white;
        border-radius: 10px;
    }

    .stSelectbox div[data-baseweb="select"] {
        background-color: #17233E;
    }

    .section-card {
        padding: 20px;
        background: #17233E;
        border: 1px solid #293B61;
        border-radius: 15px;
        margin-bottom: 15px;
    }

    .small-label {
        color: #A5B4FC;
        font-size: 13px;
        font-weight: 600;
    }

    div[data-testid="stDownloadButton"] button {
        background: #17233E;
        color: white;
        border: 1px solid #7657F6;
        border-radius: 10px;
    }

    hr {
        border-color: #293B61;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown("""
<div class="hero">
    <div class="hero-title">🎨 AI Content Studio</div>
    <div class="hero-subtitle">
        Create professional captions, AI posters and promotional
        videos with the power of Generative AI.
    </div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# LOAD CONFIGURATION
# --------------------------------------------------

secrets_path = (
    Path(__file__).resolve().parent
    / ".streamlit"
    / "secrets.toml"
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

try:
    with secrets_path.open("rb") as file:
        config = tomllib.load(file)

except (OSError, ValueError) as error:
    st.error(f"Cannot read configuration: {secrets_path}")
    st.error(str(error))
    st.stop()


for key in ["GEMINI_API_KEY", "STABILITY_API_KEY"]:
    if not isinstance(config.get(key), str) or not config[key].strip():
        st.error(f"Missing or empty configuration: {key}")
        st.info(f"Edit your file: {secrets_path}")
        st.stop()


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

for key, default in {
    "brief": "",
    "content": None,
    "poster": None,
    "video": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# --------------------------------------------------
# SIDEBAR SETTINGS
# --------------------------------------------------

with st.sidebar:

    st.title("⚙️ Studio Settings")

    st.markdown("### Content preferences")

    tone = st.selectbox(
        "Writing tone",
        [
            "Professional",
            "Creative",
            "Friendly",
            "Energetic",
            "Inspirational",
            "Minimal"
        ]
    )

    platform = st.multiselect(
        "Target platforms",
        [
            "Instagram",
            "WhatsApp",
            "Facebook",
            "LinkedIn"
        ],
        default=["Instagram", "WhatsApp"]
    )

    poster_style = st.selectbox(
        "Poster design style",
        [
            "Modern 3D illustration",
            "Cinematic photography",
            "Minimalist design",
            "Futuristic digital art",
            "Premium advertising",
            "Vibrant creative illustration"
        ]
    )

    colour_theme = st.selectbox(
        "Colour theme",
        [
            "Navy and Gold",
            "Purple and Blue",
            "Black and Neon",
            "Orange and White",
            "Green and White"
        ]
    )

    st.divider()

    st.caption("AI Content Studio | Powered by Gemini and Stability AI")


# --------------------------------------------------
# CAMPAIGN INPUTS
# --------------------------------------------------

st.subheader("🚀 Create Your Campaign")

col1, col2 = st.columns(2)

with col1:

    idea = st.text_input(
        "💡 Campaign Idea",
        "Campus Creator Club",
        max_chars=70
    )

    audience = st.text_input(
        "👥 Target Audience",
        "College Students",
        max_chars=100
    )

with col2:

    cta = st.text_input(
        "🎯 Call to Action",
        "Join us and Start Creating Better India",
        max_chars=100
    )

    additional_details = st.text_area(
        "📝 Additional Campaign Details",
        placeholder="Add event details, benefits, location or other verified information...",
        max_chars=500,
        height=100
    )


brief = (
    f"Idea: {idea}. "
    f"Audience: {audience}. "
    f"Call to action: {cta}. "
    f"Additional details: {additional_details}."
)


# Reset previous outputs when campaign details change

if st.session_state.brief != brief:

    st.session_state.update(
        brief=brief,
        content=None,
        poster=None,
        video=None
    )


if not all(value.strip() for value in [idea, audience, cta]):
    st.info("Please complete the campaign idea, audience and CTA.")
    st.stop()


st.divider()


# --------------------------------------------------
# HELPER FUNCTION: FONT
# --------------------------------------------------

def get_font(size):

    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf"
    ]

    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            pass

    return ImageFont.load_default(size=size)


# --------------------------------------------------
# HELPER FUNCTION: POSTER CREATION
# --------------------------------------------------

def create_poster(art, idea, audience, cta, colour_theme):

    width, height = 1080, 1920

    themes = {
        "Navy and Gold": ("#071D3F", "#FFD447"),
        "Purple and Blue": ("#211047", "#A78BFA"),
        "Black and Neon": ("#101010", "#39FFB6"),
        "Orange and White": ("#8B3200", "#FFD9A0"),
        "Green and White": ("#073B32", "#B8F5D0")
    }

    background, accent = themes[colour_theme]

    poster = Image.new(
        "RGB",
        (width, height),
        background
    )

    art = ImageOps.fit(
        art,
        (width, 1400),
        method=Image.Resampling.LANCZOS
    )

    poster.paste(art, (0, 0))

    # Add dark overlay to improve text readability

    overlay = Image.new("RGBA", (width, 1400), (0, 0, 0, 45))
    poster.paste(overlay, (0, 0), overlay)

    draw = ImageDraw.Draw(poster)

    # Accent line

    draw.rounded_rectangle(
        (65, 1460, 300, 1472),
        radius=6,
        fill=accent
    )

    # Campaign title

    draw.multiline_text(
        (65, 1510),
        textwrap.fill(idea, 25),
        font=get_font(68),
        fill=accent,
        spacing=15
    )

    # Audience

    draw.text(
        (65, 1690),
        f"CREATED FOR: {audience.upper()[:45]}",
        font=get_font(27),
        fill="#D8E2F5"
    )

    # CTA

    draw.rounded_rectangle(
        (65, 1760, 1015, 1870),
        radius=20,
        fill=accent
    )

    draw.multiline_text(
        (90, 1790),
        textwrap.fill(cta, 40),
        font=get_font(32),
        fill=background,
        spacing=8
    )

    return poster


# --------------------------------------------------
# MAIN WORKSPACE
# --------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "✍️ AI Captions",
    "🖼️ AI Poster",
    "🎬 Promo Video"
])


# ==================================================
# TAB 1: GEMINI CONTENT GENERATION
# ==================================================

with tab1:

    st.subheader("✍️ AI Marketing Content Generator")

    st.write(
        "Generate platform-ready marketing captions and a "
        "15-second promotional script."
    )

    if st.button("✨ Generate Captions & Script", key="generate_text"):

        if not platform:
            st.warning("Select at least one target platform.")
        else:

            prompt = f"""
You are an expert digital marketing strategist,
creative copywriter and social media content specialist.

Create high-quality promotional content using the campaign
information below.

CAMPAIGN INFORMATION:
{brief}

TARGET PLATFORMS:
{", ".join(platform)}

WRITING TONE:
{tone}

YOUR TASK:

1. INSTAGRAM CAPTION
Write an engaging Instagram caption.
Use a powerful opening hook, natural language,
relevant emojis and suitable hashtags.

2. WHATSAPP CAPTION
Write a concise, attractive WhatsApp promotional message.
Make it easy to read and encourage people to take action.

3. FACEBOOK CAPTION
Write a community-friendly promotional caption.

4. LINKEDIN CAPTION
Write a professional promotional caption.

5. 15-SECOND PROMOTIONAL VIDEO SCRIPT
Create a short script divided into:
0-5 seconds: Attention-grabbing opening.
5-10 seconds: Main message and benefit.
10-15 seconds: Strong call to action.

IMPORTANT RULES:
- Do not invent event dates, locations, prices, links or statistics.
- Use only information supplied in the campaign details.
- Never make unsupported promises.
- Keep the writing natural and human.
- Avoid repetitive sentences.
- Make every caption suitable for its platform.
- Make the script realistic for a 15-second video.
- Use clear headings for each section.
"""

            try:

                with st.spinner("Gemini is creating your campaign content..."):

                    client = genai.Client(
                        api_key=config["GEMINI_API_KEY"].strip()
                    )

                    result = client.interactions.create(
                        model=config.get(
                            "TEXT_MODEL",
                            "gemini-3.5-flash-lite"
                        ),
                        input=prompt
                    )

                    if not result.output_text:
                        raise ValueError("Gemini returned no text.")

                    st.session_state.content = result.output_text

                st.success("Your campaign content is ready!")

            except Exception as error:
                st.error(f"Content generation failed: {error}")


    if st.session_state.content:

        st.divider()

        st.subheader("✨ Generated Campaign Content")

        st.markdown(st.session_state.content)

        st.download_button(
            "📥 Download Campaign Content",
            st.session_state.content,
            file_name="Campaign_Content.txt",
            mime="text/plain"
        )


# ==================================================
# TAB 2: STABILITY AI POSTER GENERATION
# ==================================================

with tab2:

    st.subheader("🖼️ AI Promotional Poster Generator")

    st.write(
        "Create professional promotional artwork using "
        "Stable Diffusion 3.5."
    )

    if st.button("🎨 Generate AI Poster", key="generate_poster"):

        poster_prompts = {

            "Navy and Gold":
                "deep navy blue and elegant gold accents",

            "Purple and Blue":
                "rich purple and electric blue accents",

            "Black and Neon":
                "deep black background and vibrant neon accents",

            "Orange and White":
                "warm orange and clean white accents",

            "Green and White":
                "rich green and elegant white accents"
        }

        prompt = f"""
Create a premium, visually stunning promotional advertising
illustration for the following campaign:

CAMPAIGN: {idea}
TARGET AUDIENCE: {audience}

VISUAL STYLE:
{poster_style}

COLOUR PALETTE:
{poster_prompts[colour_theme]}

ART DIRECTION:
- Professional commercial advertising quality.
- Strong visual hierarchy.
- Beautiful cinematic lighting.
- Rich depth and realistic shadows.
- Sophisticated colour grading.
- Carefully balanced composition.
- High visual detail.
- Modern creative direction.
- Visually communicate creativity, innovation and community.
- Suitable for a college promotional campaign.
- Portrait composition, 2:3 aspect ratio.

IMPORTANT:
- Focus on the campaign concept.
- Avoid random objects and visual clutter.
- No text, letters, logos, watermarks or typography.
- Do not create fake brand identities.
- Make the artwork visually appealing and professional.
"""

        try:

            with st.spinner(
                "Stability AI is creating your professional artwork..."
            ):

                response = requests.post(

                    "https://api.stability.ai/v2beta/stable-image/generate/sd3",

                    headers={
                        "Authorization": (
                            f"Bearer {config['STABILITY_API_KEY'].strip()}"
                        ),
                        "Accept": "image/*"
                    },

                    files={"none": ""},

                    data={
                        "prompt": prompt,
                        "model": "sd3.5-large-turbo",
                        "aspect_ratio": "2:3",
                        "output_format": "png"
                    },

                    timeout=(10, 120)
                )

                response.raise_for_status()

                art = Image.open(
                    io.BytesIO(response.content)
                ).convert("RGB")

                poster = create_poster(
                    art,
                    idea,
                    audience,
                    cta,
                    colour_theme
                )

                output = io.BytesIO()

                poster.save(
                    output,
                    format="PNG",
                    optimize=True
                )

                st.session_state.poster = output.getvalue()
                st.session_state.video = None

            st.success("Your AI poster is ready!")

        except requests.Timeout:

            st.error(
                "Stability AI timed out. Please try again."
            )

        except requests.HTTPError as error:

            st.error(
                f"Stability API returned HTTP {error.response.status_code}"
            )

            st.code(
                error.response.text[:1500],
                language="text"
            )

        except Exception as error:

            st.error(f"Poster generation failed: {error}")


    if st.session_state.poster:

        st.divider()

        st.subheader("✨ Your Generated Poster")

        st.image(
            st.session_state.poster,
            use_container_width=True
        )

        st.download_button(
            "📥 Download HD Poster",
            st.session_state.poster,
            file_name="AI_Campaign_Poster.png",
            mime="image/png"
        )


# ==================================================
# TAB 3: VIDEO GENERATION
# ==================================================

with tab3:

    st.subheader("🎬 15-Second Promotional Video")

    st.write(
        "Convert your generated promotional poster into "
        "a 15-second MP4 video."
    )

    if not st.session_state.poster:

        st.info(
            "First generate your AI poster in the AI Poster tab. "
            "Then come back here to export your video."
        )

    else:

        st.image(
            st.session_state.poster,
            width=250
        )

        st.markdown("### Video settings")

        st.write("Duration: 15 seconds")
        st.write("Format: MP4")
        st.write("Resolution: 1080 × 1920")
        st.write("Animation: Smooth fade-in and fade-out")

        if st.button(
            "🎬 Export 15-Second Video",
            key="generate_video"
        ):

            try:

                with st.spinner("FFmpeg is exporting your video..."):

                    with tempfile.TemporaryDirectory() as folder:

                        source = Path(folder) / "poster.png"
                        target = Path(folder) / "promo.mp4"

                        source.write_bytes(
                            st.session_state.poster
                        )

                        subprocess.run(

                            [
                                imageio_ffmpeg.get_ffmpeg_exe(),

                                "-y",

                                "-loop", "1",

                                "-framerate", "24",

                                "-i", str(source),

                                "-t", "15",

                                "-vf",
                                "scale=1080:1920,"
                                "fade=t=in:st=0:d=0.5,"
                                "fade=t=out:st=14.5:d=0.5,"
                                "format=yuv420p",

                                "-r", "24",

                                "-c:v", "libx264",

                                "-preset", "ultrafast",

                                "-pix_fmt", "yuv420p",

                                "-movflags", "+faststart",

                                str(target)
                            ],

                            check=True,
                            capture_output=True,
                            timeout=60
                        )

                        st.session_state.video = target.read_bytes()

                st.success("Your promotional video is ready!")

            except subprocess.CalledProcessError as error:

                st.error("FFmpeg video export failed.")

                st.code(
                    error.stderr.decode(errors="replace")[-1500:],
                    language="text"
                )

            except Exception as error:

                st.error(f"Video export failed: {error}")


    if st.session_state.video:

        st.divider()

        st.subheader("✨ Video Preview")

        st.video(st.session_state.video)

        st.download_button(
            "📥 Download Promotional Video",
            st.session_state.video,
            file_name="AI_Promotional_Video.mp4",
            mime="video/mp4"
        )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.markdown(
    """
    <div style="text-align:center; color:#94A3B8; padding:15px;">
        🎨 <b>AI Content Studio</b><br>
        Create • Design • Promote<br>
        <small>Powered by Gemini AI, Stability AI and FFmpeg</small>
    </div>
    """,
    unsafe_allow_html=True
)
