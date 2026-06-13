"""
Exterior Design Studio
======================

A professional, real-time exterior visualization tool for roofing contractors.
The contractor uploads a photo of a home, selects design changes from a clean
sidebar (siding, roof, doors, shutters, garage), and generates photorealistic
previews with OpenAI's GPT-image-1. Results can be compared, presented to the
client, exported to a branded PDF proposal, and shared via link.

Run with:  streamlit run app.py
"""

import base64
import io
import os
import json
import uuid
import datetime
import contextlib
import random
import functools

import requests
import streamlit as st
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from fpdf import FPDF

# Premium UI component libraries.
from streamlit_extras.stylable_container import stylable_container
from streamlit_card import card

# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=api_key)

# Brand palette.
GOLD = "#c9a84c"
GOLD_HOVER = "#dcbf6a"
BG = "#0f0f0f"
PANEL = "#1e1e1e"
CARD = "#161616"
BORDER = "#2a2a2a"


# --------------------------------------------------------------------------- #
# Option catalogs
# --------------------------------------------------------------------------- #
ELEMENT_COLORS = {
    "Siding": ["Keep as is", "White", "Beige", "Gray", "Navy Blue", "Black", "Brown", "Green", "Red", "Yellow", "Custom"],
    "Roof": ["Keep as is", "Black", "Charcoal", "Brown", "Gray", "Green", "Red", "Blue", "White", "Custom"],
    "Front Door": ["Keep as is", "Black", "White", "Red", "Navy Blue", "Forest Green", "Yellow", "Orange", "Purple", "Natural Wood", "Custom"],
    "Shutters": ["Keep as is", "Black", "White", "Green", "Navy Blue", "Brown", "Gray", "Red", "Custom"],
    "Garage Door": ["Keep as is", "White", "Black", "Gray", "Brown", "Beige", "Navy Blue", "Custom"],
}

ELEMENT_STYLES = {
    "Siding": ["Keep as is", "Board and batten", "Brick", "Stucco", "Cedar shingles", "Vinyl lap", "Stone veneer", "Metal panel", "Custom"],
    "Roof": ["Keep as is", "Asphalt shingles", "Slate tiles", "Clay tiles", "Metal standing seam", "Wood shake", "Copper", "Custom"],
    "Front Door": ["Keep as is", "Solid panel", "Glass panels", "Carriage style", "Modern flat", "Craftsman", "Arched", "Custom"],
    "Shutters": ["Keep as is", "Louvered", "Board and batten", "Raised panel", "Flat panel", "Remove shutters entirely", "Custom"],
    "Garage Door": ["Keep as is", "Raised panel", "Carriage style", "Modern flat", "Full glass", "Wood plank", "Custom"],
}

ELEMENTS = list(ELEMENT_COLORS.keys())

CUSTOM_ELEMENT_COLORS = ELEMENT_COLORS["Siding"]  # generic color list for saved custom elements
CUSTOM_ELEMENT_STYLES = ["Keep as is", "Match existing", "Custom"]


# --------------------------------------------------------------------------- #
# Theme (single injected CSS block)
# --------------------------------------------------------------------------- #
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700;800&display=swap');

/* ---- Base ---------------------------------------------------------- */
.stApp { background:#0f0f0f; color:#ffffff; font-family:'Inter',sans-serif; }
.block-container { padding-top:2.2rem; padding-bottom:3rem; max-width:1320px; }

/* Hide default chrome */
[data-testid="stHeader"] { background:transparent; height:0; }
[data-testid="stToolbar"] { display:none; }
#MainMenu, footer { visibility:hidden; }

/* ---- Sidebar ------------------------------------------------------- */
[data-testid="stSidebar"] { background:#1a1a1a; border-right:1px solid #2a2a2a; }
[data-testid="stSidebar"] .block-container { padding-top:1rem; }
section[data-testid="stSidebar"] { width:400px !important; min-width:400px !important; }
section[data-testid="stSidebar"] > div { width:400px !important; min-width:400px !important; }

/* ---- Typography helpers ------------------------------------------- */
.app-title { font-family:'Playfair Display',serif; font-size:48px; font-weight:800;
             color:#ffffff; line-height:1.05; margin:0; letter-spacing:-1px; }
.app-sub   { font-family:'Inter',sans-serif; color:#888888; font-size:15px; margin-top:6px; }
.gold-rule { height:2px; width:260px; border:none; margin:16px 0 26px;
             background:linear-gradient(90deg,#c9a84c,rgba(201,168,76,0)); }
.section-title { font-family:'Playfair Display',serif; color:#ffffff; font-size:22px;
                 font-weight:700; margin:20px 0 12px; }
.brand { font-family:'Playfair Display',serif; color:#ffffff; font-size:24px; line-height:1;
         padding:4px 2px 2px; font-weight:800; }
.brand span { display:block; color:#c9a84c; font-size:12px; letter-spacing:7px;
              font-family:'Inter',sans-serif; font-weight:600; margin-top:4px; }
.sb-h { color:#c9a84c; font-size:11px; letter-spacing:2px; font-weight:700;
        margin:14px 0 8px; text-transform:uppercase; }

/* ---- Buttons ------------------------------------------------------- */
.stButton>button, .stDownloadButton>button {
    background:#1e1e1e; color:#ffffff; border:1px solid #2a2a2a; border-radius:10px;
    font-weight:500; padding:.5rem 1rem; transition:all .18s ease; font-family:'Inter',sans-serif;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    border-color:#c9a84c; color:#c9a84c; box-shadow:0 3px 14px rgba(201,168,76,.18);
}
[data-testid="stBaseButton-primary"] {
    background:#c9a84c !important; color:#0f0f0f !important; border:none !important;
    font-weight:700 !important; border-radius:10px !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background:#dcbf6a !important; color:#0f0f0f !important;
    box-shadow:0 6px 20px rgba(201,168,76,.4) !important; transform:translateY(-1px);
}

/* ---- Inputs -------------------------------------------------------- */
.stTextInput input, .stNumberInput input, .stTextArea textarea {
    background:#1e1e1e !important; color:#ffffff !important; border:1px solid #2a2a2a !important;
    border-radius:8px !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:#5a5a5a !important; }
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
    border-color:#c9a84c !important; box-shadow:0 0 0 1px #c9a84c !important;
}
[data-baseweb="input"], [data-baseweb="base-input"] { background:#1e1e1e !important; }

/* ---- Select boxes -------------------------------------------------- */
[data-baseweb="select"] > div {
    background:#1e1e1e !important; border:1px solid #2a2a2a !important;
    border-radius:8px !important; color:#ffffff !important;
}
[data-baseweb="select"] > div:focus-within { border-color:#c9a84c !important; }
[data-baseweb="select"] * { color:#ffffff !important; }
[data-baseweb="popover"] [role="listbox"] { background:#1e1e1e !important; border:1px solid #2a2a2a; }
[data-baseweb="popover"] li { background:#1e1e1e !important; color:#ddd !important; }
[data-baseweb="popover"] li:hover { background:rgba(201,168,76,.15) !important; color:#fff !important; }

/* ---- Labels -------------------------------------------------------- */
label, .stSlider label, [data-testid="stWidgetLabel"] p { color:#bbbbbb !important; font-weight:500; }

/* ---- Expander ------------------------------------------------------ */
[data-testid="stExpander"] { background:#1e1e1e; border:1px solid #2a2a2a; border-radius:10px; }
[data-testid="stExpander"] summary { color:#ffffff !important; }
[data-testid="stExpander"] summary:hover { color:#c9a84c !important; }

/* ---- Slider -------------------------------------------------------- */
[data-testid="stSlider"] [role="slider"] {
    background:#c9a84c !important; border-color:#c9a84c !important;
    box-shadow:0 0 0 .2rem rgba(201,168,76,.3) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="progressbar"] { background:#c9a84c !important; }
[data-testid="stSlider"] [data-testid="stThumbValue"] { color:#c9a84c !important; }

/* ---- File uploader ------------------------------------------------- */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {
    background:#161616 !important; border:1px dashed #2a2a2a !important; border-radius:12px;
}
[data-testid="stFileUploader"] * { color:#aaaaaa !important; }

/* ---- Progress / checkbox / misc ----------------------------------- */
[data-testid="stProgress"] > div > div > div { background:#c9a84c !important; }
input[type="checkbox"] { accent-color:#c9a84c; }
[data-baseweb="checkbox"] div[data-checked="true"] { background:#c9a84c !important; border-color:#c9a84c !important; }
hr { border-color:#2a2a2a; }

/* ---- Quote table --------------------------------------------------- */
table.quote { width:100%; border-collapse:collapse; font-family:'Inter',sans-serif;
              font-size:14px; border-radius:10px; overflow:hidden; }
table.quote th { background:#c9a84c; color:#0f0f0f; padding:11px 14px; text-align:left; font-weight:700; }
table.quote td { padding:11px 14px; border-bottom:1px solid #2a2a2a; color:#dddddd; background:#161616; }
table.quote tr.total td { background:#1f1b12; color:#c9a84c; font-weight:700;
                          border-top:2px solid #c9a84c; font-size:15px; }

/* ---- Loading spinner fallback ------------------------------------- */
.gold-spinner { width:48px; height:48px; border:4px solid #2a2a2a; border-top-color:#c9a84c;
                border-radius:50%; animation:spin 1s linear infinite; margin:10px auto; }
@keyframes spin { to { transform:rotate(360deg); } }

/* ---- Scrollbar ----------------------------------------------------- */
::-webkit-scrollbar { height:8px; width:8px; }
::-webkit-scrollbar-thumb { background:#2a2a2a; border-radius:8px; }
::-webkit-scrollbar-thumb:hover { background:#c9a84c; }

/* ---- Ant-design segmented overrides ------------------------------- */
div[data-testid="stCustomComponentV1"] { background-color:#1a1a1a !important; border-radius:0 !important; }
div[data-testid="stCustomComponentV1"] iframe { background-color:#1a1a1a !important; background:#1a1a1a !important; }
.ant-segmented { background-color:#1e1e1e !important; border:1px solid #2a2a2a !important; border-radius:8px !important; }
.ant-segmented-item { color:#cccccc !important; }
.ant-segmented-item-selected { background-color:#c9a84c !important; color:#000000 !important; }
.ant-segmented-thumb { background-color:#c9a84c !important; }
iframe { background-color:transparent !important; background:transparent !important; border:none !important; }
.ant-segmented-item-label { color:#ffffff !important; font-weight:500 !important; }
.ant-segmented-item:not(.ant-segmented-item-selected) .ant-segmented-item-label { color:#cccccc !important; }
.ant-segmented-item-selected .ant-segmented-item-label { color:#000000 !important; font-weight:600 !important; }

/* ---- Tabs ---------------------------------------------------------- */
div[data-testid="stTabs"] {
    background-color:#0f0f0f !important;
}
div[data-testid="stTabs"] > div {
    background-color:#0f0f0f !important;
}
button[data-baseweb="tab"] {
    background-color:#0f0f0f !important;
    color:#888888 !important;
}
button[data-baseweb="tab"]:hover {
    background-color:#1e1e1e !important;
    color:#c9a84c !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background-color:#0f0f0f !important;
    color:#c9a84c !important;
    border-bottom:2px solid #c9a84c !important;
}
div[data-testid="stTabsContent"] {
    background-color:#0f0f0f !important;
}
div[role="tabpanel"] {
    background-color:#0f0f0f !important;
}
div[role="tablist"] {
    background-color:#0f0f0f !important;
    border-bottom:1px solid #2a2a2a !important;
}

/* ---- File uploader ------------------------------------------------- */
section[data-testid="stFileUploader"] {
    background-color:#1e1e1e !important;
    border:1px solid #2a2a2a !important;
    border-radius:8px !important;
}
section[data-testid="stFileUploader"] button,
section[data-testid="stFileUploader"] button:active,
section[data-testid="stFileUploader"] button:focus,
section[data-testid="stFileUploader"] button:visited,
section[data-testid="stFileUploader"] button:not(:hover) {
    background-color:#c9a84c !important;
    color:#000000 !important;
    border:none !important;
    border-radius:6px !important;
}
section[data-testid="stFileUploader"] button:hover {
    background-color:#b8923d !important;
}
section[data-testid="stFileUploader"] label {
    color:#888888 !important;
}
div[data-testid="stFileUploadDropzone"] {
    background-color:#1e1e1e !important;
    border:1px dashed #2a2a2a !important;
    border-radius:8px !important;
}
div[data-testid="stFileUploadDropzone"] p {
    color:#888888 !important;
}
</style>
"""

# Reusable stylable_container CSS snippets.
IMAGE_FRAME_CSS = """
{
    background:#161616; border:1px solid rgba(201,168,76,0.30); border-radius:18px;
    padding:16px; box-shadow:0 10px 36px rgba(0,0,0,0.55);
}
img { border-radius:12px; }
"""

ACTIONS_CSS = """
button {
    background:#161616 !important; border:1px solid #2a2a2a !important;
    border-radius:999px !important; color:#dddddd !important; font-weight:500 !important;
}
button:hover {
    border-color:#c9a84c !important; color:#c9a84c !important;
    box-shadow:0 3px 14px rgba(201,168,76,0.18) !important;
}
"""

EDIT_CARD_CSS = """
{
    background:#161616; border:1px solid #2a2a2a; border-left:3px solid #c9a84c;
    border-radius:10px; padding:6px 14px 16px 14px; margin-bottom:9px;
    width:100% !important; box-sizing:border-box !important; overflow:visible !important;
    min-height:56px !important;
}
* { box-sizing:border-box !important; }
"""

GOLD_FRAME_CSS = """
{
    background:#161616; border:1px solid rgba(201,168,76,0.35); border-radius:14px; padding:10px;
}
img { border-radius:10px; }
"""

TIMELINE_CSS = """
[data-testid="stColumn"] {
    background:#161616; border:1px solid #2a2a2a; border-radius:14px; padding:12px;
    transition:all .18s ease;
}
[data-testid="stColumn"]:hover {
    border-color:#c9a84c; box-shadow:0 6px 20px rgba(201,168,76,0.18);
}
img { border-radius:8px; }
"""

REMOVE_BTN_CSS = """
button {
    background:transparent !important; border:1px solid #c0392b !important; color:#e74c3c !important;
}
button:hover {
    background:rgba(192,57,43,0.12) !important; color:#ff6b5e !important; border-color:#e74c3c !important;
}
"""

ICON_BTN_CSS = """
button {
    width:44px !important; height:44px !important; min-height:44px !important;
    border-radius:50% !important; padding:0 !important; margin:4px 0 !important;
    background:#1e1e1e !important; border:1px solid rgba(201,168,76,0.35) !important;
    color:#c9a84c !important; font-size:11px !important; font-weight:700 !important;
    display:flex !important; align-items:center !important; justify-content:center !important;
    font-family:Inter,sans-serif !important;
}
button:hover {
    background:rgba(201,168,76,0.10) !important; border-color:#c9a84c !important;
    box-shadow:0 0 12px rgba(201,168,76,0.25) !important;
}
[data-testid="stDownloadButton"] button {
    width:44px !important; height:44px !important; border-radius:50% !important;
    padding:0 !important; background:#1e1e1e !important;
    border:1px solid rgba(201,168,76,0.35) !important;
    color:#c9a84c !important; font-size:11px !important; font-weight:700 !important;
}
"""


# --------------------------------------------------------------------------- #
# Loading spinner
# --------------------------------------------------------------------------- #
_LOADING_MESSAGES = [
    "Reimagining your home...",
    "Crafting your vision...",
    "Bringing it to life...",
    "Designing something beautiful...",
    "Almost there...",
    "Making it happen...",
    "Working some magic...",
    "Painting the picture...",
]


@contextlib.contextmanager
def lottie_loading(_message=None):
    """Context manager — shows an st.spinner with a random loading message."""
    msg = random.choice(_LOADING_MESSAGES)
    with st.spinner(msg):
        yield


def img_to_data_uri(image_bytes):
    """Encode raw image bytes as a base64 PNG data URI for HTML/components."""
    return "data:image/png;base64," + base64.b64encode(image_bytes).decode()


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _pdf_safe(text):
    """Make a string safe for fpdf2 core (latin-1) fonts by stripping
    characters that cannot be encoded, replacing them with '?'."""
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def describe_edit(edit):
    """Return a short human-readable description of a single edit, e.g.
    "White Brick" or "Navy Blue Board and batten". Resolves custom values."""
    color = edit.get("color", "Keep as is")
    style = edit.get("style", "Keep as is")

    if color == "Custom":
        color = (edit.get("custom_color") or "").strip() or "Custom color"
    if style == "Custom":
        style = (edit.get("custom_style") or "").strip() or "Custom style"

    parts = []
    if color and color != "Keep as is":
        parts.append(color)
    if style and style != "Keep as is":
        parts.append(style)
    return " ".join(parts) if parts else "Keep as is"


# --------------------------------------------------------------------------- #
# Core function: build_instruction
# --------------------------------------------------------------------------- #
def build_instruction(edit_history, custom_instructions):
    """
    Build a single combined natural-language instruction string for GPT-image-1.

    Parameters
    ----------
    edit_history : list[dict]
        List of edit dicts. Each edit may carry ``color``, ``style``,
        ``custom_color`` and ``custom_style`` keys for a named ``element``.
    custom_instructions : list[dict]
        List of free-form instruction dicts, each with a ``text`` key.

    Behaviour
    ---------
    For every edit, the color and style are combined into a short description
    (e.g. "white brick", "navy blue board and batten"). When ``color`` or
    ``style`` is set to "Custom", the corresponding ``custom_color`` /
    ``custom_style`` text is used instead. Edits where both color and style are
    "Keep as is" are skipped entirely. All custom instruction texts are appended
    at the end.

    Returns
    -------
    str
        A complete, photorealism-preserving instruction string.
    """
    changes = []
    for edit in edit_history:
        color = edit.get("color", "Keep as is")
        style = edit.get("style", "Keep as is")

        # Skip the edit entirely when nothing changes.
        if color in (None, "", "Keep as is") and style in (None, "", "Keep as is"):
            continue

        description = describe_edit(edit).lower()
        if not description or description == "keep as is":
            continue

        element = edit.get("element", "element").lower()
        changes.append(f"change the {element} to {description}")

    # Append all custom instructions verbatim.
    for instr in custom_instructions:
        text = (instr.get("text") or "").strip()
        if text:
            changes.append(text)

    changes_text = "; ".join(changes) if changes else "make no visual changes"

    instruction = (
        f"This is a photo of a house. {changes_text}. "
        "Do not change anything else — preserve the exact roofline, all windows, "
        "all doors, the lawn, the sky, the trees, the driveway, and all other "
        "elements exactly as they are. The result must look photorealistic with "
        "the same lighting and perspective as the original photo. "
        "Pay special attention to keeping the lawn, grass, and landscaping completely "
        "photorealistic and natural — do not over-saturate or stylize the greenery in any way. "
        "Do not crop, zoom in, or change the framing of the image in any way. "
        "Keep the exact same field of view and composition as the original photo."
    )
    return instruction


# --------------------------------------------------------------------------- #
# Core function: apply_watermark
# --------------------------------------------------------------------------- #
def apply_watermark(pil_image, watermark_text):
    """
    Stamp semi-transparent watermark text into the bottom-right corner.

    Parameters
    ----------
    pil_image : PIL.Image.Image
        The image to watermark.
    watermark_text : str
        Contractor branding text. If falsy, the image is returned unchanged.

    Behaviour
    ---------
    Font size is roughly 2% of the image width. The text is white at ~60%
    opacity with a subtle dark shadow behind it for legibility.

    Returns
    -------
    PIL.Image.Image
        The watermarked image (RGB).
    """
    if not watermark_text:
        return pil_image

    base = pil_image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(12, int(base.width * 0.02))
    font = None
    for font_name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = max(8, int(base.width * 0.02))
    x = base.width - text_w - margin
    y = base.height - text_h - margin - bbox[1]

    # Subtle shadow for readability.
    draw.text((x + 2, y + 2), watermark_text, font=font, fill=(0, 0, 0, 130))
    # Main text: white at ~60% opacity.
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 153))

    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


# --------------------------------------------------------------------------- #
# Core function: edit_image
# --------------------------------------------------------------------------- #
def edit_image(original_image_bytes, edit_history, custom_instructions):
    """
    Generate an edited preview from the ORIGINAL image using GPT-image-1.

    Parameters
    ----------
    original_image_bytes : bytes
        The pristine source photo. This is always used as the base — never a
        previously edited result — so edits never compound.
    edit_history : list[dict]
        Current set of element edits.
    custom_instructions : list[dict]
        Current set of free-form custom instructions.

    Behaviour
    ---------
    Builds the combined instruction via :func:`build_instruction`, converts the
    source bytes to an in-memory PNG (named ``image.png`` and rewound), and
    calls ``client.images.edit``. Both ``b64_json`` and ``url`` response formats
    are handled. If ``st.session_state.watermark_text`` is set, the result is
    watermarked via :func:`apply_watermark` before being returned.

    Returns
    -------
    tuple[PIL.Image.Image, bytes]
        The final PIL image and its PNG-encoded bytes.
    """
    instruction = build_instruction(edit_history, custom_instructions)

    # Letterbox the source image into a 1024x1024 square with black padding.
    source = Image.open(io.BytesIO(original_image_bytes)).convert("RGB")
    orig_w, orig_h = source.size
    scale = 1024 / max(orig_w, orig_h)
    scaled_w = round(orig_w * scale)
    scaled_h = round(orig_h * scale)
    resized = source.resize((scaled_w, scaled_h), Image.LANCZOS)
    pad_x = (1024 - scaled_w) // 2
    pad_y = (1024 - scaled_h) // 2
    square = Image.new("RGB", (1024, 1024), (0, 0, 0))
    square.paste(resized, (pad_x, pad_y))

    image_file = io.BytesIO()
    square.save(image_file, format="PNG")
    image_file.name = "image.png"
    image_file.seek(0)

    response = client.images.edit(
        model="gpt-image-1",
        image=image_file,
        prompt=instruction,
        n=1,
        size="1024x1024",
    )

    data = response.data[0]
    if getattr(data, "b64_json", None):
        result_bytes = base64.b64decode(data.b64_json)
    elif getattr(data, "url", None):
        result_bytes = requests.get(data.url, timeout=60).content
    else:
        raise ValueError("OpenAI response contained neither b64_json nor url.")

    # Crop out the black padding bars to restore the original aspect ratio.
    result_square = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    result_image = result_square.crop((pad_x, pad_y, pad_x + scaled_w, pad_y + scaled_h))
    result_image = result_image.resize((orig_w, orig_h), Image.LANCZOS)

    watermark_text = st.session_state.get("watermark_text", "")
    if watermark_text:
        result_image = apply_watermark(result_image, watermark_text)

    out = io.BytesIO()
    result_image.save(out, format="PNG")
    return result_image, out.getvalue()


# --------------------------------------------------------------------------- #
# Core function: generate_variations
# --------------------------------------------------------------------------- #
def generate_variations(original_image_bytes, edit_history, custom_instructions, element, options):
    """
    Generate up to three style variations for a single element.

    Parameters
    ----------
    original_image_bytes : bytes
        The pristine source photo (used as the base for every variation).
    edit_history : list[dict]
        The base edits to which each option is temporarily added.
    custom_instructions : list[dict]
        Custom instructions applied to every variation.
    element : str
        The element being varied (e.g. "Siding").
    options : list[str]
        Up to three style options to try for that element.

    Behaviour
    ---------
    For each option a temporary edit is appended to a copy of ``edit_history``
    and :func:`edit_image` is called. A Streamlit progress bar tracks progress.

    Returns
    -------
    list[tuple[PIL.Image.Image, bytes, str]]
        One ``(pil_image, image_bytes, option_label)`` tuple per successful
        variation (up to three).
    """
    options = list(options)[:3]
    results = []
    progress = st.progress(0.0, text="Generating variations…")

    for index, option in enumerate(options):
        temp_edit = {
            "id": str(uuid.uuid4()),
            "element": element,
            "color": "Keep as is",
            "style": option,
            "custom_color": "",
            "custom_style": "",
            "note": "",
            "price": 0.0,
            "selected": False,
        }
        temp_history = list(edit_history) + [temp_edit]
        try:
            pil_image, image_bytes = edit_image(
                original_image_bytes, temp_history, custom_instructions
            )
            results.append((pil_image, image_bytes, option))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Variation '{option}' failed: {exc}")
        progress.progress((index + 1) / max(1, len(options)),
                          text=f"Generated {index + 1} of {len(options)}…")

    progress.empty()
    return results


# --------------------------------------------------------------------------- #
# Core function: export_pdf
# --------------------------------------------------------------------------- #
def export_pdf(project_name, original_image_bytes, current_image_bytes,
               edit_history, custom_instructions, watermark_text):
    """
    Build a professional, multi-page PDF proposal with fpdf2 and return bytes.

    Pages
    -----
    1. Cover         — project name, date, contractor (watermark) name.
    2. Before/After  — original and current images side by side with labels.
    3. Scope of work — numbered list of every edit (element, description, note)
                       plus any custom instructions.
    4. Investment    — line-item pricing table, total, contractor footer.

    Returns
    -------
    bytes
        The encoded PDF document.
    """
    contractor = _pdf_safe(watermark_text) or "Your Roofing Company"
    project_name = _pdf_safe(project_name) or "Exterior Design Proposal"
    today = datetime.datetime.now().strftime("%B %d, %Y")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    page_w = pdf.w - 2 * pdf.l_margin

    # ---- Page 1: Cover ---------------------------------------------------- #
    pdf.add_page()
    pdf.set_fill_color(23, 37, 84)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.ln(70)
    pdf.set_font("Helvetica", "B", 34)
    pdf.multi_cell(page_w, 16, "Exterior Design Studio", align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 20)
    pdf.multi_cell(page_w, 12, project_name, align="C")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 14)
    pdf.multi_cell(page_w, 10, f"Prepared: {today}", align="C")
    pdf.ln(2)
    pdf.multi_cell(page_w, 10, contractor, align="C")

    # ---- Page 2: Before / After ------------------------------------------ #
    pdf.add_page()
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Before & After", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    col_w = (page_w - 8) / 2
    img_y = pdf.get_y() + 8
    label_y = pdf.get_y()

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(pdf.l_margin, label_y)
    pdf.cell(col_w, 8, "BEFORE", align="C")
    pdf.set_xy(pdf.l_margin + col_w + 8, label_y)
    pdf.cell(col_w, 8, "AFTER", align="C")

    try:
        if original_image_bytes:
            before = Image.open(io.BytesIO(original_image_bytes)).convert("RGB")
            pdf.image(before, x=pdf.l_margin, y=img_y, w=col_w)
        if current_image_bytes:
            after = Image.open(io.BytesIO(current_image_bytes)).convert("RGB")
            pdf.image(after, x=pdf.l_margin + col_w + 8, y=img_y, w=col_w)
    except Exception as exc:  # noqa: BLE001
        pdf.set_xy(pdf.l_margin, img_y)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(page_w, 8, f"(Images unavailable: {_pdf_safe(exc)})")

    # ---- Page 3: Scope of Work ------------------------------------------- #
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Scope of Work", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 12)

    line_no = 0
    for edit in edit_history:
        if edit.get("color", "Keep as is") == "Keep as is" and \
           edit.get("style", "Keep as is") == "Keep as is":
            continue
        line_no += 1
        element = _pdf_safe(edit.get("element", ""))
        desc = _pdf_safe(describe_edit(edit))
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(page_w, 8, f"{line_no}. {element}: {desc}")
        note = (edit.get("note") or "").strip()
        if note:
            pdf.set_font("Helvetica", "I", 11)
            pdf.set_x(pdf.l_margin + 6)
            pdf.multi_cell(page_w - 6, 7, f"Note: {_pdf_safe(note)}")
        pdf.ln(1)

    for instr in custom_instructions:
        text = (instr.get("text") or "").strip()
        if not text:
            continue
        line_no += 1
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(page_w, 8, f"{line_no}. Custom: {_pdf_safe(text)}")
        pdf.ln(1)

    if line_no == 0:
        pdf.set_font("Helvetica", "I", 12)
        pdf.multi_cell(page_w, 8, "No changes specified yet.")

    # ---- Page 4: Investment Summary -------------------------------------- #
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Investment Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    desc_w = page_w * 0.70
    price_w = page_w * 0.30

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(23, 37, 84)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(desc_w, 10, "  Item", border=0, fill=True)
    pdf.cell(price_w, 10, "Price  ", border=0, align="R", fill=True,
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)

    total = 0.0
    row_shade = False
    pdf.set_font("Helvetica", "", 12)
    for edit in edit_history:
        price = float(edit.get("price") or 0.0)
        if price <= 0:
            continue
        element = _pdf_safe(edit.get("element", ""))
        desc = _pdf_safe(describe_edit(edit))
        total += price
        if row_shade:
            pdf.set_fill_color(238, 242, 248)
        else:
            pdf.set_fill_color(255, 255, 255)
        row_shade = not row_shade
        pdf.cell(desc_w, 9, f"  {element}: {desc}", border=0, fill=True)
        pdf.cell(price_w, 9, f"${price:,.2f}  ", border=0, align="R", fill=True,
                 new_x="LMARGIN", new_y="NEXT")

    if total == 0:
        pdf.set_font("Helvetica", "I", 12)
        pdf.cell(0, 9, "  No priced line items.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(220, 228, 240)
    pdf.cell(desc_w, 11, "  Total Investment", border=0, fill=True)
    pdf.cell(price_w, 11, f"${total:,.2f}  ", border=0, align="R", fill=True,
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(16)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Prepared by: {contractor}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Date: {today}", new_x="LMARGIN", new_y="NEXT")

    output = pdf.output()
    return bytes(output)


# --------------------------------------------------------------------------- #
# State helpers
# --------------------------------------------------------------------------- #
def init_state():
    """Initialise every session_state key used by the app. Widget-bound keys
    that render conditionally (per-element controls, watermark, zoom) are
    re-anchored each run so their values survive navigation/tab switches."""
    st.session_state.setdefault("original_image_bytes", None)
    st.session_state.setdefault("current_image_bytes", None)
    st.session_state.setdefault("edit_history", [])
    st.session_state.setdefault("custom_instructions", [])
    st.session_state.setdefault("variations", [])
    st.session_state.setdefault("projects", {})
    st.session_state.setdefault("current_project_name", None)
    st.session_state.setdefault("favorite_presets", [])
    st.session_state.setdefault("compare_variation_ids", [])

    # Auxiliary UI-only keys.
    st.session_state.setdefault("show_slider", False)
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("uploaded_sig", None)
    st.session_state.setdefault("last_batch_ids", [])
    st.session_state.setdefault("active_element", "Siding")
    st.session_state.setdefault("saved_custom_elements", [])

    # Re-anchor conditionally-rendered widget keys so they persist.
    anchored = {
        "watermark_text": "",
        "custom_element_text": "",
        "custom_element_description": "",
    }
    for element in ELEMENTS:
        anchored[f"{element}_color"] = "Keep as is"
        anchored[f"{element}_style"] = "Keep as is"
        anchored[f"{element}_custom_color"] = ""
        anchored[f"{element}_custom_style"] = ""
        anchored[f"{element}_price"] = 0.0
        anchored[f"{element}_note"] = ""
    # Also anchor widget keys for any saved custom element tabs.
    for element in st.session_state.get("saved_custom_elements", []):
        anchored[f"{element}_color"] = "Keep as is"
        anchored[f"{element}_style"] = "Keep as is"
        anchored[f"{element}_custom_color"] = ""
        anchored[f"{element}_custom_style"] = ""
        anchored[f"{element}_price"] = 0.0
        anchored[f"{element}_note"] = ""
    for key, default in anchored.items():
        st.session_state[key] = st.session_state.get(key, default)


def apply_pending_preset():
    """Apply a queued favorite preset before any element widget renders.

    Favorites live in a different sidebar section from the element editor, so
    they cannot set the dropdown widgets directly. They queue a request that is
    applied here, at the top of the run, before those widgets are instantiated.
    """
    pending = st.session_state.pop("_pending_preset", None)
    if not pending:
        return
    element = pending["element"]
    if pending.get("color") in ELEMENT_COLORS.get(element, []):
        st.session_state[f"{element}_color"] = pending["color"]
    if pending.get("style") in ELEMENT_STYLES.get(element, []):
        st.session_state[f"{element}_style"] = pending["style"]
    st.session_state["active_element"] = element


def build_edits_from_state():
    """Construct the edit_history list from the current per-element selections,
    skipping any element where both color and style are 'Keep as is'.
    Also includes saved custom element tabs and the freeform 'Something else?' entry."""
    edits = []
    all_elements = ELEMENTS + list(st.session_state.get("saved_custom_elements", []))
    for element in all_elements:
        color = st.session_state.get(f"{element}_color", "Keep as is")
        style = st.session_state.get(f"{element}_style", "Keep as is")
        if color == "Keep as is" and style == "Keep as is":
            continue
        edits.append({
            "id": str(uuid.uuid4()),
            "element": element,
            "color": color,
            "style": style,
            "custom_color": st.session_state.get(f"{element}_custom_color", ""),
            "custom_style": st.session_state.get(f"{element}_custom_style", ""),
            "note": st.session_state.get(f"{element}_note", ""),
            "price": float(st.session_state.get(f"{element}_price", 0.0) or 0.0),
            "selected": False,
        })

    # Freeform "Something else?" field — only included if a description is provided
    # and the element name isn't already handled as a saved custom element tab.
    custom_el = (st.session_state.get("custom_element_text") or "").strip()
    custom_el_desc = (st.session_state.get("custom_element_description") or "").strip()
    if custom_el and custom_el_desc and custom_el not in st.session_state.get("saved_custom_elements", []):
        edits.append({
            "id": str(uuid.uuid4()),
            "element": custom_el,
            "color": "Keep as is",
            "style": "Custom",
            "custom_color": "",
            "custom_style": custom_el_desc,
            "note": "",
            "price": 0.0,
            "selected": False,
        })
    return edits


def add_variation(name, image_bytes, edits, customs):
    """Append a new variation snapshot to session_state.variations."""
    variation = {
        "id": str(uuid.uuid4()),
        "name": name,
        "image_bytes": image_bytes,
        "edits": [dict(e) for e in edits],
        "custom_instructions": [dict(c) for c in customs],
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    st.session_state.variations.append(variation)
    return variation


def run_generate():
    """Build the edit history from state, call GPT-image-1 once, store the
    result as the current image and as a new variation."""
    if not st.session_state.original_image_bytes:
        st.sidebar.error("Upload a house photo first.")
        return
    edits = build_edits_from_state()
    customs = st.session_state.custom_instructions
    if not edits and not customs:
        st.sidebar.warning("Select at least one change before generating.")
        return
    try:
        with lottie_loading("GPT-image-1 is crafting your design..."):
            _, image_bytes = edit_image(
                st.session_state.original_image_bytes, edits, customs
            )
        st.session_state.current_image_bytes = image_bytes
        st.session_state.edit_history = edits
        count = len(st.session_state.variations) + 1
        add_variation(f"Design {count}", image_bytes, edits, customs)
        st.session_state.last_batch_ids = []
        st.sidebar.success("Preview generated.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Generation failed: {exc}")


# --------------------------------------------------------------------------- #
# Sidebar sections (rendered inside the option-menu dispatch)
# --------------------------------------------------------------------------- #
def sb_design():
    """Design panel: element segmented tabs (built-in + saved custom + Custom),
    per-element controls, custom instructions, and generate buttons."""
    saved_custom = st.session_state.get("saved_custom_elements", [])
    all_elements_for_tabs = ELEMENTS + saved_custom + ["Custom"]

    st.markdown("<div class='sb-h'>Elements</div>", unsafe_allow_html=True)

    current = st.session_state.get("active_element", "Siding")
    if current not in all_elements_for_tabs:
        current = ELEMENTS[0]

    _EL_BTN_BASE = (
        " border:none !important; border-radius:6px !important;"
        " width:100% !important; padding:4px 2px !important;"
        " font-size:11px !important; white-space:nowrap !important;"
        " overflow:hidden !important; text-overflow:ellipsis !important;"
        " min-height:32px !important; line-height:1.2 !important;"
        " box-sizing:border-box !important;"
    )
    _EL_ACTIVE_CSS = (
        f"button {{ background-color:#c9a84c !important; color:#000000 !important;"
        f" font-weight:700 !important;{_EL_BTN_BASE} }}"
        " button:hover { background-color:#c9a84c !important; color:#000000 !important; }"
    )
    _EL_INACTIVE_CSS = (
        f"button {{ background-color:#1e1e1e !important; color:#aaaaaa !important;"
        f" font-weight:500 !important;{_EL_BTN_BASE} }}"
        " button:hover { background-color:#252525 !important; color:#c9a84c !important; }"
    )

    def _el_button(col, el_name):
        is_active = current == el_name
        with col:
            with stylable_container(f"eltab_{el_name}", _EL_ACTIVE_CSS if is_active else _EL_INACTIVE_CSS):
                if st.button(el_name, key=f"eltab_btn_{el_name}", use_container_width=True):
                    st.session_state.active_element = el_name
                    st.rerun()

    # Zero out inter-column padding so buttons fill available width
    st.markdown(
        "<style>"
        " section[data-testid='stSidebar'] div[data-testid='stHorizontalBlock']"
        " > div[data-testid='stColumn'] { padding-left:1px !important; padding-right:1px !important; }"
        " section[data-testid='stSidebar'] div[data-testid='stHorizontalBlock']"
        " > div[data-testid='stColumn'] > div { gap:0 !important; }"
        "</style>",
        unsafe_allow_html=True,
    )

    # Fixed two rows for the built-in elements; saved custom + Custom spill into extra rows
    base_rows = [all_elements_for_tabs[:3], all_elements_for_tabs[3:6]]
    overflow = all_elements_for_tabs[6:]  # saved custom elements beyond the first two rows
    for row_items in base_rows:
        for col, el_name in zip(st.columns(3), row_items):
            _el_button(col, el_name)
    for i in range(0, len(overflow), 3):
        for col, el_name in zip(st.columns(3), overflow[i:i+3]):
            _el_button(col, el_name)

    element = current

    if element == "Custom":
        # ---- Freeform custom element tab --------------------------------- #
        st.markdown(
            "<div style='color:#fff;font-weight:600;margin:6px 0 2px;font-size:15px;'>"
            "Custom Element</div>",
            unsafe_allow_html=True,
        )
        el_col, save_col = st.columns([4, 1])
        el_col.text_input(
            "Element name", key="custom_element_text",
            placeholder="e.g. chimney, porch columns...",
            label_visibility="collapsed",
        )
        custom_el_text = (st.session_state.get("custom_element_text") or "").strip()
        if custom_el_text:
            st.text_input(
                "Describe the change", key="custom_element_description",
                placeholder="e.g. paint it black with a modern style",
            )
        if save_col.button("Save", key="save_custom_element", help="Add as permanent element tab"):
            new_el = (st.session_state.get("custom_element_text") or "").strip()
            if new_el and new_el not in st.session_state.get("saved_custom_elements", []):
                st.session_state.saved_custom_elements.append(new_el)
                for k, v in [(f"{new_el}_color", "Keep as is"), (f"{new_el}_style", "Keep as is"),
                             (f"{new_el}_custom_color", ""), (f"{new_el}_custom_style", ""),
                             (f"{new_el}_price", 0.0), (f"{new_el}_note", "")]:
                    st.session_state[k] = v
                st.session_state.active_element = new_el
                st.toast(f"Added '{new_el}' as an element tab.")
                st.rerun()
            elif new_el:
                st.toast(f"'{new_el}' is already saved as a tab.")

    else:
        # ---- Standard element UI ----------------------------------------- #
        st.markdown(
            f"<div style='color:#fff;font-weight:600;margin:6px 0 2px;font-size:15px;'>"
            f"{element}</div>",
            unsafe_allow_html=True,
        )

        is_custom_el = element in saved_custom
        color_opts = CUSTOM_ELEMENT_COLORS if is_custom_el else ELEMENT_COLORS[element]
        style_opts = CUSTOM_ELEMENT_STYLES if is_custom_el else ELEMENT_STYLES[element]

        for key, default in [(f"{element}_color", "Keep as is"), (f"{element}_style", "Keep as is"),
                             (f"{element}_custom_color", ""), (f"{element}_custom_style", ""),
                             (f"{element}_price", 0.0), (f"{element}_note", "")]:
            st.session_state.setdefault(key, default)

        st.selectbox("Color", color_opts, key=f"{element}_color")
        if st.session_state[f"{element}_color"] == "Custom":
            st.text_input("Describe the color", key=f"{element}_custom_color",
                          placeholder="e.g. sage green")

        st.selectbox("Style / Texture", style_opts, key=f"{element}_style")
        if st.session_state[f"{element}_style"] == "Custom":
            st.text_input("Describe the style/texture", key=f"{element}_custom_style",
                          placeholder="e.g. reclaimed barn wood")

        with st.expander("Add to Quote", expanded=False):
            st.number_input("Estimated price ($)", min_value=0.0, step=100.0,
                            key=f"{element}_price")
            st.text_input("Note (material, brand, etc.)", key=f"{element}_note",
                          placeholder="optional")

        if is_custom_el:
            star_col, rm_col, hint_col = st.columns([1, 1, 3])
        else:
            star_col, hint_col = st.columns([1, 4])
            rm_col = None

        with star_col:
            with stylable_container(
                "starbtn",
                "button { background:transparent !important; border:1px solid #c9a84c !important;"
                " color:#c9a84c !important; font-size:13px !important; border-radius:10px !important; }"
                " button:hover { background:rgba(201,168,76,0.15) !important; }",
            ):
                star = st.button("Save", key=f"fav_{element}",
                                 help="Save this color + style as a favorite")

        if rm_col is not None:
            with rm_col:
                with stylable_container("rmbtn_" + element[:8], REMOVE_BTN_CSS):
                    if st.button("Remove", key=f"rm_el_{element}",
                                 help="Remove this custom element tab"):
                        st.session_state.saved_custom_elements = [
                            e for e in saved_custom if e != element
                        ]
                        st.session_state.active_element = ELEMENTS[0]
                        st.rerun()

        hint_col.caption("Save to Favorites" if not is_custom_el else "Save / Remove tab")

        if star:
            st.session_state.favorite_presets.append({
                "id": str(uuid.uuid4()),
                "element": element,
                "color": st.session_state.get(f"{element}_color", "Keep as is"),
                "style": st.session_state.get(f"{element}_style", "Keep as is"),
            })
            st.toast(f"Saved favorite for {element}.")

    # ---- Custom instructions -------------------------------------------- #
    st.markdown("<div class='sb-h'>Add Something Custom</div>", unsafe_allow_html=True)
    custom_text = st.text_area(
        "Custom instruction", key="custom_instruction_input", height=80,
        placeholder="e.g. Add a lamppost on the left, add window boxes with flowers",
        label_visibility="collapsed",
    )
    if st.button("Add Instruction", key="add_custom", use_container_width=True):
        text = (custom_text or "").strip()
        if text:
            st.session_state.custom_instructions.append({
                "id": str(uuid.uuid4()), "text": text, "selected": False,
            })
            st.rerun()

    for instr in list(st.session_state.custom_instructions):
        row_text, row_x = st.columns([5, 1])
        row_text.markdown(
            f"<div style='color:#c9a84c;font-size:13px;padding-top:6px;'>{instr['text']}</div>",
            unsafe_allow_html=True,
        )
        if row_x.button("X", key=f"del_ci_{instr['id']}"):
            st.session_state.custom_instructions = [
                c for c in st.session_state.custom_instructions if c["id"] != instr["id"]
            ]
            st.rerun()

    # ---- Generate -------------------------------------------------------- #
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Generate Preview", type="primary", use_container_width=True, key="gen_preview"):
        run_generate()

    if st.button("Generate 3 Variations", use_container_width=True, key="gen_var"):
        _run_generate_variations()


def _run_generate_variations():
    """Find the first changed element and generate three style variations of
    it (logic preserved from the original sidebar implementation)."""
    if not st.session_state.original_image_bytes:
        st.error("Upload a house photo first.")
        return
    target = None
    for element in ELEMENTS:
        if (st.session_state.get(f"{element}_color") != "Keep as is" or
                st.session_state.get(f"{element}_style") != "Keep as is"):
            target = element
            break
    if not target:
        st.warning("Select a change on at least one element first.")
        return
    style_opts = [s for s in ELEMENT_STYLES[target] if s not in ("Keep as is", "Custom")][:3]
    base_edits = build_edits_from_state()
    results = generate_variations(
        st.session_state.original_image_bytes, base_edits,
        st.session_state.custom_instructions, target, style_opts,
    )
    batch = []
    for _, image_bytes, option in results:
        var = add_variation(f"{target}: {option}", image_bytes,
                            base_edits, st.session_state.custom_instructions)
        batch.append(var["id"])
    st.session_state.last_batch_ids = batch
    if results:
        st.session_state.current_image_bytes = results[0][1]
        st.success(f"Generated {len(results)} variations of {target}.")


def sb_projects():
    """Save and load full project snapshots."""
    st.markdown("<div class='sb-h'>Project</div>", unsafe_allow_html=True)
    project_name = st.text_input("Project Name", key="current_project_name_input",
                                 placeholder="e.g. Johnson Residence")

    if st.button("Save Project", type="primary", use_container_width=True):
        name = (project_name or "").strip() or "Untitled Project"
        saved_custom = list(st.session_state.get("saved_custom_elements", []))
        st.session_state.projects[name] = {
            "name": name,
            "original_image_bytes": st.session_state.original_image_bytes,
            "current_image_bytes": st.session_state.current_image_bytes,
            "variations": [dict(v) for v in st.session_state.variations],
            "favorite_presets": [dict(p) for p in st.session_state.favorite_presets],
            "edit_history": [dict(e) for e in st.session_state.edit_history],
            "custom_instructions": [dict(c) for c in st.session_state.custom_instructions],
            "saved_custom_elements": saved_custom,
            "element_state": {
                k: st.session_state.get(k)
                for el in ELEMENTS
                for k in (f"{el}_color", f"{el}_style", f"{el}_custom_color",
                          f"{el}_custom_style", f"{el}_price", f"{el}_note")
            },
            "custom_element_state": {
                k: st.session_state.get(k)
                for el in saved_custom
                for k in (f"{el}_color", f"{el}_style", f"{el}_custom_color",
                          f"{el}_custom_style", f"{el}_price", f"{el}_note")
            },
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        st.session_state.current_project_name = name
        st.success(f"Saved '{name}'.")

    st.markdown("<div class='sb-h'>Load</div>", unsafe_allow_html=True)
    saved_names = ["—"] + list(st.session_state.projects.keys())
    chosen = st.selectbox("Load Project", saved_names, key="load_project_select",
                          label_visibility="collapsed")
    if chosen != "—" and chosen != st.session_state.get("_last_loaded"):
        proj = st.session_state.projects.get(chosen)
        if proj:
            st.session_state.original_image_bytes = proj.get("original_image_bytes")
            st.session_state.current_image_bytes = proj.get("current_image_bytes")
            st.session_state.variations = [dict(v) for v in proj.get("variations", [])]
            st.session_state.favorite_presets = [dict(p) for p in proj.get("favorite_presets", [])]
            st.session_state.edit_history = [dict(e) for e in proj.get("edit_history", [])]
            st.session_state.custom_instructions = [dict(c) for c in proj.get("custom_instructions", [])]
            st.session_state.saved_custom_elements = proj.get("saved_custom_elements", [])
            for key, value in (proj.get("element_state") or {}).items():
                st.session_state[key] = value
            for key, value in (proj.get("custom_element_state") or {}).items():
                st.session_state[key] = value
            st.session_state.current_project_name = proj.get("name")
            st.session_state["_last_loaded"] = chosen
            st.success(f"Loaded '{chosen}'.")
            st.rerun()

    if st.session_state.projects:
        st.caption(f"{len(st.session_state.projects)} saved project(s)")


def sb_favorites():
    """Quick-apply and manage saved favorite presets."""
    st.markdown("<div class='sb-h'>Favorite Presets</div>", unsafe_allow_html=True)
    if not st.session_state.favorite_presets:
        st.caption("Star a color + style combo in the Design panel to save it here.")
        return
    for preset in list(st.session_state.favorite_presets):
        label = f"{preset['element']}: {preset['color']} / {preset['style']}"
        cols = st.columns([5, 1])
        if cols[0].button(label, key=f"apply_{preset['id']}", use_container_width=True):
            st.session_state["_pending_preset"] = preset
            st.rerun()
        if cols[1].button("X", key=f"delfav_{preset['id']}"):
            st.session_state.favorite_presets = [
                p for p in st.session_state.favorite_presets if p["id"] != preset["id"]
            ]
            st.rerun()


def sb_quote():
    """Compact quote summary in the sidebar."""
    quote_table(compact=True)


def sb_settings():
    """Watermark and other settings."""
    st.markdown("<div class='sb-h'>Contractor Branding</div>", unsafe_allow_html=True)
    st.text_input("Watermark", key="watermark_text",
                  placeholder="Ryan's Roofing | 801-555-0123",
                  label_visibility="collapsed")
    st.caption("Stamped onto every generated image and shown on the PDF.")
    st.markdown("<div class='sb-h'>Tips</div>", unsafe_allow_html=True)
    st.caption("• Use Favorites to reuse your go-to combos.\n\n"
               "• Export a PDF to leave with the homeowner.\n\n"
               "• Use the Custom tab to visualize any element.")


def render_sidebar():
    """Render sidebar navigation and dispatch to the active section."""
    st.session_state.setdefault("active_sidebar_section", "Design")

    _NAV_ITEMS = [
        ("Design",    "✦"),
        ("Projects",  "▤"),
        ("Favorites", "★"),
        ("Quote",     "▣"),
        ("Settings",  "⚙"),
    ]

    _NAV_BTN_BASE = (
        " border:none !important; border-radius:8px !important;"
        " width:260px !important;"
        " padding:10px 10px 10px 16px !important;"
        " font-size:15px !important; margin-bottom:2px !important;"
        " display:flex !important; align-items:center !important;"
        " justify-content:flex-start !important; text-align:left !important;"
    )
    _NAV_ACTIVE = (
        f"button {{ background-color:#c9a84c !important; color:#000000 !important;"
        f" font-weight:700 !important;{_NAV_BTN_BASE} }}"
        " button:hover { background-color:#c9a84c !important; color:#000000 !important; }"
        " button p { text-align:left !important; width:100% !important; margin:0 !important; font-size:15px !important; }"
    )
    _NAV_INACTIVE = (
        f"button {{ background-color:#1a1a1a !important; color:#aaaaaa !important;"
        f" font-weight:500 !important;{_NAV_BTN_BASE} }}"
        " button:hover { background-color:#c9a84c !important; color:#000000 !important; }"
        " button p { text-align:left !important; width:100% !important; margin:0 !important; font-size:15px !important; }"
    )

    with st.sidebar:
        st.markdown(
            "<div class='brand'>EXTERIOR<span>DESIGN STUDIO</span></div>",
            unsafe_allow_html=True,
        )

        for section, icon in _NAV_ITEMS:
            is_active = st.session_state.active_sidebar_section == section
            with stylable_container(f"nav_{section}", _NAV_ACTIVE if is_active else _NAV_INACTIVE):
                if st.button(f"{icon}  {section}", key=f"nav_btn_{section}", use_container_width=True):
                    st.session_state.active_sidebar_section = section
                    st.rerun()

        dispatch = {
            "Design":    sb_design,
            "Projects":  sb_projects,
            "Favorites": sb_favorites,
            "Quote":     sb_quote,
            "Settings":  sb_settings,
        }
        dispatch.get(st.session_state.active_sidebar_section, sb_design)()


# --------------------------------------------------------------------------- #
# Main-area panels
# --------------------------------------------------------------------------- #
def render_header():
    """Playfair title, Inter subtitle, and a thin gold divider."""
    st.markdown(
        "<div class='app-title'>Exterior Design Studio</div>"
        "<div class='app-sub'>Design the perfect exterior. Show clients before you build.</div>"
        "<hr class='gold-rule'>",
        unsafe_allow_html=True,
    )


def render_icon_toolbar():
    """Pure HTML toolbar: all 5 SVG circle buttons in one st.components.v1.html() call.

    Python-side actions (B/A toggle, PDF) are routed through two hidden
    Streamlit buttons. The iframe JS sends window.parent.postMessage then immediately
    finds the matching hidden button by its unique text content and calls .click() on it.
    Download uses a base64 data-URI <a> tag. Share uses the clipboard API directly.
    """
    _HIDE = (
        "button{position:absolute!important;left:-9999px!important;"
        "width:1px!important;height:1px!important;opacity:0!important;"
        "pointer-events:none!important;}"
    )

    # Hidden Streamlit buttons — visually removed, still clickable via JS .click().
    with stylable_container("hb_ba_w",  _HIDE):
        _ba   = st.button("__tb_ba__",   key="hb_ba")
    with stylable_container("hb_pdf_w", _HIDE):
        _pdf  = st.button("__tb_pdf__",  key="hb_pdf")
    if _ba:
        st.session_state.show_slider = not st.session_state.show_slider
    if _pdf:
        try:
            st.session_state.pdf_bytes = export_pdf(
                st.session_state.current_project_name or "Exterior Design",
                st.session_state.original_image_bytes,
                st.session_state.current_image_bytes,
                st.session_state.edit_history,
                st.session_state.custom_instructions,
                st.session_state.watermark_text,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"PDF export failed: {exc}")
    # Data URIs for download and share payload.
    img_b64   = base64.b64encode(st.session_state.current_image_bytes).decode()
    share_enc = base64.b64encode(json.dumps({
        "edits":   st.session_state.edit_history,
        "customs": st.session_state.custom_instructions,
    }).encode()).decode()

    # Shared inline styles.
    BTN = (
        "width:44px;height:44px;border-radius:50%;background:#1e1e1e;"
        "border:1px solid #c9a84c;cursor:pointer;"
        "display:flex;align-items:center;justify-content:center;"
        "transition:background .18s,box-shadow .18s;"
        "padding:0;box-sizing:border-box;"
    )
    HVR = (
        'onmouseover="this.style.background=\'rgba(201,168,76,0.10)\';'
        'this.style.boxShadow=\'0 0 12px rgba(201,168,76,0.25)\';" '
        'onmouseout="this.style.background=\'#1e1e1e\';this.style.boxShadow=\'none\';"'
    )

    html = f"""
<div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:4px 0;">

  <button title="Before / After" style="{BTN}" {HVR} onclick="act('ba')">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <rect x="2" y="2" width="12" height="12" fill="none" stroke="#c9a84c" stroke-width="1.5"/>
      <rect x="6" y="6" width="12" height="12" fill="none" stroke="#c9a84c" stroke-width="1.5"/>
    </svg>
  </button>

  <a href="data:image/png;base64,{img_b64}" download="exterior_design.png"
     title="Download" style="{BTN};text-decoration:none;" {HVR}
     onclick="window.parent.postMessage({{action:'dl'}},'*');">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <path d="M12 3v12M6 11l6 6 6-6M4 20h16" stroke="#c9a84c" stroke-width="1.5"
            fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </a>

  <button title="Export PDF" style="{BTN}" {HVR} onclick="act('pdf')">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <path d="M4 4h10l4 4v14H4V4z" stroke="#c9a84c" stroke-width="1.5" fill="none"/>
      <path d="M14 4v4h4" stroke="#c9a84c" stroke-width="1.5" fill="none"/>
      <path d="M8 12h6M8 15h4" stroke="#c9a84c" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
  </button>

  <button title="Copy Share Link" style="{BTN}" {HVR} onclick="shareFn()">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <path d="M4 12v6h14v-6M12 3v10M8 7l4-4 4 4" stroke="#c9a84c" stroke-width="1.5"
            fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>

</div>
<script>
function act(action) {{
  window.parent.postMessage({{action: action}}, '*');
  var btns = window.parent.document.querySelectorAll('button');
  for (var i = 0; i < btns.length; i++) {{
    if ((btns[i].textContent || '').trim() === '__tb_' + action + '__') {{
      btns[i].click();
      return;
    }}
  }}
}}
function shareFn() {{
  window.parent.postMessage({{action: 'share'}}, '*');
  var url = window.parent.location.origin + window.parent.location.pathname
            + '?design={share_enc}';
  if (window.parent.navigator.clipboard) {{
    window.parent.navigator.clipboard.writeText(url);
  }}
}}
</script>
"""
    st.components.v1.html(html, height=300)


def render_before_after_slider():
    """Render a pure HTML/CSS/JS before-after slider with a gold divider."""
    original = st.session_state.original_image_bytes
    current = st.session_state.current_image_bytes
    if not original or not current:
        st.info("Generate a preview to use the before/after slider.")
        return

    b64_before = base64.b64encode(original).decode()
    b64_after = base64.b64encode(current).decode()

    try:
        img = Image.open(io.BytesIO(current))
        aspect = img.height / img.width
    except Exception:  # noqa: BLE001
        aspect = 0.66
    height = int(700 * aspect)

    html = f"""
    <div style="position:relative;width:700px;max-width:100%;height:{height}px;
                overflow:hidden;border-radius:14px;user-select:none;
                border:1px solid rgba(201,168,76,0.35);
                box-shadow:0 8px 26px rgba(0,0,0,0.5);" id="ba-wrap">
      <img src="data:image/png;base64,{b64_before}"
           style="position:absolute;top:0;left:0;width:700px;height:{height}px;
                  object-fit:cover;" draggable="false"/>
      <div id="ba-after" style="position:absolute;top:0;left:0;width:50%;
           height:{height}px;overflow:hidden;">
        <img src="data:image/png;base64,{b64_after}"
             style="width:700px;height:{height}px;object-fit:cover;" draggable="false"/>
      </div>
      <div id="ba-divider" style="position:absolute;top:0;left:50%;width:3px;
           height:{height}px;background:#c9a84c;cursor:ew-resize;
           box-shadow:0 0 10px rgba(201,168,76,0.8);"></div>
      <div style="position:absolute;top:12px;left:12px;background:rgba(0,0,0,0.6);
           color:#fff;padding:4px 12px;border-radius:6px;font-family:Inter,sans-serif;
           font-size:12px;letter-spacing:1px;">BEFORE</div>
      <div style="position:absolute;top:12px;right:12px;background:rgba(201,168,76,0.85);
           color:#0f0f0f;padding:4px 12px;border-radius:6px;font-family:Inter,sans-serif;
           font-size:12px;letter-spacing:1px;font-weight:600;">AFTER</div>
    </div>
    <script>
      const wrap = document.getElementById('ba-wrap');
      const afterBox = document.getElementById('ba-after');
      const divider = document.getElementById('ba-divider');
      let dragging = false;
      function setPos(clientX) {{
        const rect = wrap.getBoundingClientRect();
        let x = clientX - rect.left;
        x = Math.max(0, Math.min(x, rect.width));
        const pct = (x / rect.width) * 100;
        afterBox.style.width = pct + '%';
        divider.style.left = pct + '%';
      }}
      divider.addEventListener('mousedown', () => dragging = true);
      window.addEventListener('mouseup', () => dragging = false);
      window.addEventListener('mousemove', (e) => {{ if (dragging) setPos(e.clientX); }});
      wrap.addEventListener('click', (e) => setPos(e.clientX));
    </script>
    """
    st.components.v1.html(html, height=height + 20)


def render_variation_cards():
    """Display the most recent batch of 3 variations as clickable cards."""
    ids = st.session_state.get("last_batch_ids", [])
    if not ids:
        return
    variations = [v for v in st.session_state.variations if v["id"] in ids]
    if not variations:
        return

    st.markdown("<div class='section-title'>Latest Variations</div>", unsafe_allow_html=True)
    cols = st.columns(len(variations))
    for col, var in zip(cols, variations):
        with col:
            clicked = card(
                title=var["name"],
                text="Use this design",
                image=img_to_data_uri(var["image_bytes"]),
                key="vcard_" + var["id"],
                on_click=lambda: None,
                styles={
                    "card": {
                        "width": "100%", "height": "240px", "border-radius": "14px",
                        "border": "1px solid #2a2a2a", "margin": "0",
                        "box-shadow": "0 6px 20px rgba(0,0,0,0.5)",
                    },
                    "title": {"color": "#ffffff", "font-family": "Inter", "font-size": "15px"},
                    "text": {"color": "#c9a84c", "font-family": "Inter", "font-size": "12px"},
                    "filter": {"background-color": "rgba(0,0,0,0.45)"},
                },
            )
            if clicked and st.session_state.current_image_bytes != var["image_bytes"]:
                st.session_state.current_image_bytes = var["image_bytes"]
                st.rerun()


def render_edit_history_panel():
    """Render the editable edit-history panel with checkbox-based removal."""
    edits = st.session_state.edit_history
    customs = st.session_state.custom_instructions
    if not edits and not customs:
        st.caption("Your generated edits will appear here.")
        return

    for edit in edits:
        with stylable_container("eh_" + edit["id"], EDIT_CARD_CSS):
            c0, c1, c2, c3 = st.columns([0.6, 5, 2, 2])
            c0.checkbox("Select edit", key=f"editsel_{edit['id']}", label_visibility="collapsed")
            c1.markdown(
                f"<b style='color:#fff'>{edit['element']}</b>"
                f"<br><span style='color:#aaa;font-size:13px'>{describe_edit(edit)}</span>",
                unsafe_allow_html=True,
            )
            price = float(edit.get("price") or 0.0)
            c2.markdown(
                f"<div style='color:#c9a84c;font-weight:600;padding-top:6px'>${price:,.0f}</div>"
                if price > 0 else "<div style='color:#555;padding-top:6px'>—</div>",
                unsafe_allow_html=True,
            )
            c3.markdown(
                f"<div style='color:#888;font-size:12px;padding-top:8px'>{edit.get('note') or ''}</div>",
                unsafe_allow_html=True,
            )

    for instr in customs:
        with stylable_container("ci_" + instr["id"], EDIT_CARD_CSS):
            c0, c1 = st.columns([0.6, 9])
            c0.checkbox("Select instruction", key=f"cisel_{instr['id']}", label_visibility="collapsed")
            c1.markdown(
                f"<div style='color:#c9a84c;padding-top:6px'><i>{instr['text']}</i></div>",
                unsafe_allow_html=True,
            )

    with stylable_container("removebtn", REMOVE_BTN_CSS):
        remove = st.button("Remove Selected", key="remove_selected")
    if remove:
        remaining_edits = [e for e in edits
                           if not st.session_state.get(f"editsel_{e['id']}")]
        remaining_customs = [c for c in customs
                             if not st.session_state.get(f"cisel_{c['id']}")]
        st.session_state.edit_history = remaining_edits
        st.session_state.custom_instructions = remaining_customs
        if st.session_state.original_image_bytes and (remaining_edits or remaining_customs):
            try:
                with lottie_loading("Regenerating your design..."):
                    _, image_bytes = edit_image(
                        st.session_state.original_image_bytes,
                        remaining_edits, remaining_customs,
                    )
                st.session_state.current_image_bytes = image_bytes
                add_variation(f"Design {len(st.session_state.variations) + 1}",
                              image_bytes, remaining_edits, remaining_customs)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Regeneration failed: {exc}")
        elif not remaining_edits and not remaining_customs:
            st.session_state.current_image_bytes = st.session_state.original_image_bytes
        st.rerun()


def quote_table(compact=False):
    """Render the quote — a compact summary (sidebar) or a full dark/gold
    table (main tab). Shows only line items that have a price set."""
    priced = [e for e in st.session_state.edit_history if float(e.get("price") or 0.0) > 0]

    if compact:
        st.markdown("<div class='sb-h'>Quote</div>", unsafe_allow_html=True)
        if not priced:
            st.caption("Add prices to elements (Design > Add to Quote).")
            return
        total = sum(float(e.get("price") or 0.0) for e in priced)
        st.markdown(
            f"<div style='color:#888;font-size:13px'>{len(priced)} line item(s)</div>"
            f"<div style='color:#c9a84c;font-size:30px;font-weight:700;margin:2px 0 8px'>"
            f"${total:,.0f}</div>",
            unsafe_allow_html=True,
        )
        for edit in priced:
            st.markdown(
                "<div style='display:flex;justify-content:space-between;"
                "border-bottom:1px solid #2a2a2a;padding:5px 0;font-size:13px'>"
                f"<span style='color:#ccc'>{edit['element']}</span>"
                f"<span style='color:#c9a84c'>${float(edit['price']):,.0f}</span></div>",
                unsafe_allow_html=True,
            )
        return

    if not priced:
        st.info("Add prices to elements (in the Design panel) to build a quote.")
        return

    rows = ""
    total = 0.0
    for edit in priced:
        price = float(edit["price"])
        total += price
        rows += (
            f"<tr><td>{edit['element']}</td>"
            f"<td>{describe_edit(edit)}</td>"
            f"<td>{edit.get('note') or '—'}</td>"
            f"<td style='text-align:right'>${price:,.2f}</td></tr>"
        )
    html = (
        "<table class='quote'><thead><tr><th>Element</th><th>Description</th>"
        "<th>Note</th><th style='text-align:right'>Price</th></tr></thead><tbody>"
        f"{rows}"
        "<tr class='total'><td colspan='3'>Total Investment</td>"
        f"<td style='text-align:right'>${total:,.2f}</td></tr></tbody></table>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_compare_designs():
    """Side-by-side comparison of two saved variations in gold frames."""
    variations = st.session_state.variations
    if len(variations) < 2:
        st.caption("Generate at least two designs to compare.")
        return
    names = [v["name"] for v in variations]
    col_a, col_b = st.columns(2)
    pick_a = col_a.selectbox("Design A", names, index=0, key="cmp_a")
    pick_b = col_b.selectbox("Design B", names,
                             index=min(1, len(names) - 1), key="cmp_b")
    var_a = next((v for v in variations if v["name"] == pick_a), None)
    var_b = next((v for v in variations if v["name"] == pick_b), None)

    for col, var, pick_key in [(col_a, var_a, "pick_a"), (col_b, var_b, "pick_b")]:
        with col:
            with stylable_container("cmpframe_" + pick_key, GOLD_FRAME_CSS):
                if var:
                    st.image(var["image_bytes"], use_container_width=True)
            if var and st.button("Pick This One", key=pick_key, type="primary",
                                 use_container_width=True):
                st.session_state.current_image_bytes = var["image_bytes"]
                st.success(f"Selected '{var['name']}'.")


def render_timeline():
    """Horizontal strip of all generated variations as hover-gold cards."""
    variations = st.session_state.variations
    if not variations:
        st.caption("Your generated designs will appear here.")
        return
    with stylable_container("timeline", TIMELINE_CSS):
        cols = st.columns(max(1, len(variations)))
        for col, var in zip(cols, variations):
            with col:
                st.image(var["image_bytes"], use_container_width=True)
                st.markdown(
                    f"<div style='color:#fff;font-weight:600;font-size:13px;margin-top:6px'>"
                    f"{var['name']}</div>"
                    f"<div style='color:#777;font-size:11px'>{var['timestamp']}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Restore", key=f"restore_{var['id']}", use_container_width=True):
                    st.session_state.current_image_bytes = var["image_bytes"]
                    st.session_state.edit_history = [dict(e) for e in var.get("edits", [])]
                    st.session_state.custom_instructions = [
                        dict(c) for c in var.get("custom_instructions", [])
                    ]
                    st.rerun()


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    """Application entry point: configure the page, inject the theme, initialise
    state, and render either the presentation view or the full studio."""
    st.set_page_config(page_title="Exterior Design Studio", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    init_state()
    apply_pending_preset()

    render_sidebar()
    render_header()

    # ---- Image upload ---------------------------------------------------- #
    uploaded = st.file_uploader("Upload a house photo", type=["jpg", "jpeg", "png"])
    if uploaded is not None:
        data = uploaded.getvalue()
        signature = (uploaded.name, len(data))
        if st.session_state.uploaded_sig != signature:
            st.session_state.original_image_bytes = data
            st.session_state.current_image_bytes = data
            st.session_state.edit_history = []
            st.session_state.custom_instructions = []
            st.session_state.uploaded_sig = signature
            st.session_state.last_batch_ids = []
            st.success("Photo loaded. Use the sidebar to design.")

    if not st.session_state.current_image_bytes:
        st.info("Upload a photo of the home's exterior to begin.")
        return

    # ---- Image + icon toolbar -------------------------------------------- #
    img_col, tb_col = st.columns([13, 1])
    with img_col:
        with stylable_container("image_frame", IMAGE_FRAME_CSS):
            st.image(st.session_state.current_image_bytes, width=700)
    with tb_col:
        render_icon_toolbar()

    if st.session_state.pdf_bytes:
        st.download_button(
            "Download PDF Proposal",
            data=st.session_state.pdf_bytes,
            file_name="exterior_proposal.pdf",
            mime="application/pdf",
            key="pdf_dl",
        )

    # ---- Before/After slider --------------------------------------------- #
    if st.session_state.show_slider:
        render_before_after_slider()

    # ---- Tabbed lower panels (manual session_state tabs) ----------------- #
    st.session_state.setdefault("active_bottom_tab", "history")

    _TABS = [
        ("history",  "Edit History"),
        ("quote",    "Quote"),
        ("compare",  "Compare"),
        ("timeline", "Design History"),
    ]
    _ACTIVE_CSS = """
button {
    background-color:#c9a84c !important; color:#000000 !important;
    border:none !important; border-radius:8px 8px 0 0 !important;
    font-weight:700 !important; width:100% !important;
}
button:hover { background-color:#c9a84c !important; color:#000000 !important; }
"""
    _INACTIVE_CSS = """
button {
    background-color:#1e1e1e !important; color:#888888 !important;
    border:none !important; border-radius:8px 8px 0 0 !important;
    font-weight:500 !important; width:100% !important;
}
button:hover { background-color:#252525 !important; color:#c9a84c !important; }
"""
    tab_cols = st.columns(len(_TABS))
    for col, (tid, tlabel) in zip(tab_cols, _TABS):
        is_active = st.session_state.active_bottom_tab == tid
        with col:
            with stylable_container(f"btab_{tid}", _ACTIVE_CSS if is_active else _INACTIVE_CSS):
                if st.button(tlabel, key=f"btab_btn_{tid}", use_container_width=True):
                    st.session_state.active_bottom_tab = tid
                    st.rerun()

    active = st.session_state.active_bottom_tab
    if active == "history":
        render_edit_history_panel()
    elif active == "quote":
        quote_table(compact=False)
    elif active == "compare":
        render_compare_designs()
    elif active == "timeline":
        render_timeline()


if __name__ == "__main__":
    main()
