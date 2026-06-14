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
import math
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
    "Roof": ["Keep as is", "Black", "Charcoal", "Brown", "Gray", "Green", "Red", "Navy Blue", "White", "Custom"],
    "Front Door": ["Keep as is", "Black", "White", "Red", "Navy Blue", "Forest Green", "Yellow", "Orange", "Purple", "Natural Wood", "Custom"],
    "Shutters": ["Keep as is", "Black", "White", "Green", "Navy Blue", "Brown", "Gray", "Red", "Custom"],
    "Garage Door": ["Keep as is", "White", "Black", "Gray", "Brown", "Beige", "Navy Blue", "Custom"],
    "Gables": ["Keep as is", "White", "Black", "Gray", "Beige", "Navy", "Brown", "Green", "Red", "Yellow", "Custom"],
}

ELEMENT_STYLES = {
    "Siding": ["Keep as is", "Board and batten", "Brick", "Stucco", "Cedar shingles", "Vinyl lap", "Stone veneer", "Metal panel", "Custom"],
    "Roof": ["Keep as is", "Asphalt shingles", "Slate tiles", "Clay tiles", "Metal standing seam", "Wood shake", "Copper", "Custom"],
    "Front Door": ["Keep as is", "Solid panel", "Glass panels", "Carriage style", "Modern flat", "Craftsman", "Arched", "Custom"],
    "Shutters": ["Keep as is", "Louvered", "Board and batten", "Raised panel", "Flat panel", "Remove shutters entirely", "Custom"],
    "Garage Door": ["Keep as is", "Raised panel", "Carriage style", "Modern flat", "Full glass", "Wood plank", "Custom"],
    "Gables": ["Keep as is", "Smooth Paint", "Board and Batten", "Cedar Shingles", "Vinyl Lap", "Wood Panels", "Decorative Trim", "Match Siding", "Custom"],
}

ELEMENTS = list(ELEMENT_COLORS.keys())

CUSTOM_ELEMENT_COLORS = ELEMENT_COLORS["Siding"]  # generic color list for saved custom elements
CUSTOM_ELEMENT_STYLES = ["Keep as is", "Match existing", "Custom"]

# Color + texture pickers (replace old combined-swatch approach).
PICKER_COLORS = [
    ("White",  "#f5f0eb"),
    ("Beige",  "#d4bc94"),
    ("Gray",   "#808080"),
    ("Navy",   "#1e3a5f"),
    ("Black",  "#1a1a1a"),
    ("Brown",  "#6b4423"),
    ("Green",  "#2d5a27"),
    ("Red",    "#8b2727"),
    ("Yellow", "#c9a84c"),
]

PICKER_TEXTURES = [
    "Brick", "Stucco", "Wood Panels", "Cedar Shingles",
    "Board and Batten", "Stone Veneer", "Vinyl Lap", "Metal Panel",
]

ELEMENT_TEXTURES = {
    "Siding": [
        "Brick", "Stucco", "Wood Panels", "Cedar Shingles",
        "Board and Batten", "Stone Veneer", "Vinyl Lap", "Metal Panel", "Custom",
    ],
    "Roof": [
        "Asphalt Shingles", "Slate Tiles", "Clay Tiles", "Metal Standing Seam",
        "Wood Shake", "Copper", "Flat Membrane", "Custom",
    ],
    "Front Door": [
        "Solid Wood", "Glass Panels", "Craftsman Style", "Arched",
        "Modern Flat", "French Doors", "Steel", "Fiberglass", "Custom",
    ],
    "Shutters": [
        "Louvered", "Board and Batten", "Raised Panel",
        "Flat Panel", "Bahama Style", "Colonial", "Custom",
    ],
    "Garage Door": [
        "Raised Panel", "Carriage Style", "Modern Flat",
        "Full Glass", "Wood Plank", "Flush Panel", "Custom",
    ],
    "Gables": [
        "Smooth Paint", "Board and Batten", "Cedar Shingles",
        "Vinyl Lap", "Wood Panels", "Decorative Trim", "Match Siding", "Custom",
    ],
}


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
button[kind="header"] {
    display: none !important;
}
[data-testid="collapsedControl"] {
    display: none !important;
}
button[data-testid="baseButton-header"] {
    display: none !important;
}
/* Suppress all focus rings for overlay / swatch / element buttons */
[class*="tpick_"] button:focus,
[class*="tpick_"] button:focus-visible,
[class*="tpick_"] button:active {
    outline: none !important;
    box-shadow: none !important;
}
[class*="cpick_"] button:focus,
[class*="cpick_"] button:focus-visible,
[class*="cpick_"] button:active {
    outline: none !important;
    box-shadow: none !important;
}
[class*="eltab_"] button:focus,
[class*="eltab_"] button:focus-visible,
[class*="eltab_"] button:active {
    outline: none !important;
    box-shadow: none !important;
    border-radius: 8px !important;
}
[class*="cpkeep_"] button:focus,
[class*="cpkeep_"] button:focus-visible,
[class*="cpkeep_"] button:active {
    outline: none !important;
    box-shadow: none !important;
}
[class*="tpkeep_"] button:focus,
[class*="tpkeep_"] button:focus-visible,
[class*="tpkeep_"] button:active {
    outline: none !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] {
    transform: none !important;
    visibility: visible !important;
    display: block !important;
    min-width: 400px !important;
    width: 400px !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] {
    transform: none !important;
    margin-left: 0 !important;
    min-width: 400px !important;
}
</style>
"""

# Reusable stylable_container CSS snippets.
# Module-level references to st.empty() placeholders set in main() before
# render_sidebar() runs, so sidebar callbacks can write into the main area.
_image_placeholder = None
_var_placeholder = None   # progress bar + variation cards during generation

# Pre-encoded hero demo images (loaded once at import time).
def _load_hero_images():
    import pathlib
    before_path = pathlib.Path("/Users/georgerichards/Downloads/premier-design-custom-homes-westfield-nj-front-elevation-e1604677087354.jpg")
    after_path  = pathlib.Path("/Users/georgerichards/Downloads/before:after.jpg")
    try:
        b = base64.b64encode(before_path.read_bytes()).decode()
        a = base64.b64encode(after_path.read_bytes()).decode()
        return b, a
    except Exception:
        return None, None

_HERO_BEFORE_B64, _HERO_AFTER_B64 = _load_hero_images()

_SPINNER_HTML = """
<div style="
    width: 100%;
    height: 500px;
    background: #161616;
    border: 2px solid rgba(201,168,76,0.70);
    border-radius: 18px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
">
    <style>
    @keyframes spin {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .gold-spinner {
        width: 60px;
        height: 60px;
        border: 4px solid #2a2a2a;
        border-top: 4px solid #c9a84c;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    </style>
    <div class="gold-spinner"></div>
    <p style="color:#c9a84c; font-family:'Playfair Display',serif;
              font-size:18px; margin:0;">Crafting your design...</p>
</div>
"""

IMAGE_FRAME_CSS = [
    "{ background:#161616; border:1px solid rgba(201,168,76,0.30); border-radius:18px;"
    " padding:0; overflow:hidden; box-shadow:0 10px 36px rgba(0,0,0,0.55); }",
    "> div:first-child { margin-bottom:0 !important; }",
    "[data-testid='stImage'] { width:100% !important; max-width:none !important; }",
    "[data-testid='stImage'] > img { width:100% !important; max-width:none !important;"
    " height:auto !important; border-radius:18px; display:block; }",
]

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
        raw_color = edit.get("color", "Keep as is")
        raw_style = edit.get("style", "Keep as is")

        color = raw_color == "Custom" and ((edit.get("custom_color") or "").strip() or "Custom color") or raw_color
        style = raw_style == "Custom" and ((edit.get("custom_style") or "").strip() or "Custom style") or raw_style

        has_color = color not in (None, "", "Keep as is")
        has_style = style not in (None, "", "Keep as is")

        if not has_color and not has_style:
            continue

        element_raw = edit.get("element", "element")
        element = element_raw.lower()
        target = "gable ends and gable trim" if element_raw == "Gables" else element

        if has_color and has_style:
            changes.append(f"Change the {target} to {color.lower()} {style.lower()}")
        elif has_color:
            changes.append(
                f"Repaint the {target} to {color.lower()} — keep the exact same material, "
                f"texture, and surface pattern completely unchanged, only the color should change"
            )
        else:
            changes.append(
                f"Change the {target} material to {style.lower()} — keep the existing color tone as close as possible"
            )

    # Append all custom instructions verbatim.
    for instr in custom_instructions:
        text = (instr.get("text") or "").strip()
        if text:
            changes.append(text)

    changes_text = "; ".join(changes) if changes else "make no visual changes"

    instruction = (
        f"SYSTEM ROLE: You are the world's most precise architectural photo retouching specialist with 30 years of experience. "
        f"You have been hired to apply specific surface material changes to a photograph of a real house. "
        f"You are NOT generating a new image. You are NOT creating art. You are RETOUCHING an existing photograph. "
        f"Think of yourself as a master Photoshop retoucher who is painting new materials onto specific surfaces of an existing photograph while leaving every other pixel completely untouched. "
        f"Your reputation depends on the output being indistinguishable from the original photograph except for the explicitly requested changes. "
        f"\n\nTHE ONLY PERMITTED CHANGES — DO THESE AND NOTHING ELSE: {changes_text}. "
        f"Do not change the color or material of the gable ends or gable trim unless explicitly listed above as a change to make. "
        f"If the gables are not mentioned in the changes above, they must remain exactly as they appear in the original photo. "
        f"\n\nROOFLINE — ABSOLUTE PRESERVATION REQUIRED: "
        f"Before making any changes, mentally trace the exact silhouette of the roofline in the original photo. "
        f"Count every single roof peak, gable, dormer, hip, valley, and ridge line. "
        f"Your output must have the exact same number of peaks in the exact same positions. "
        f"The angle of every single roof slope must be mathematically identical to the original. "
        f"The height of every peak relative to the rest of the house must be identical. "
        f"The width of every gable must be identical. "
        f"The position of every dormer must be identical. "
        f"The length of every eave and soffit must be identical. "
        f"The roofline silhouette when traced against the sky must be pixel-perfect identical to the original. "
        f"Any deviation in the roofline is an automatic failure of this task. "
        f"\n\nWINDOWS — ABSOLUTE PRESERVATION REQUIRED: "
        f"Before making any changes, count every single window in the original photo including all upper floor windows, lower floor windows, dormer windows, garage windows, and any other windows. "
        f"Your output must have the exact same total number of windows. "
        f"Every window must be in the exact same position relative to the walls and other architectural elements. "
        f"Every window must be the exact same size as in the original. "
        f"Every window must have the exact same number of panes and muntin pattern as in the original. "
        f"Window frames must be the exact same color and style as in the original unless explicitly asked to change them. "
        f"The spacing between windows must be identical. "
        f"Any window that is missing, moved, resized, or altered in any way is an automatic failure of this task. "
        f"\n\nPORCH AND COLUMNS — ABSOLUTE PRESERVATION REQUIRED: "
        f"The porch must be exactly the same depth, width, and height as in the original. "
        f"Every column must be in the exact same position with the exact same diameter and height. "
        f"The porch ceiling, beams, and any decorative elements must be identical. "
        f"The porch floor and steps must be identical in size, shape, and material. "
        f"\n\nGARAGE — PRESERVATION REQUIRED UNLESS EXPLICITLY ASKED TO CHANGE: "
        f"The garage opening must be exactly the same width and height as in the original. "
        f"The garage door panels, windows, and hardware must match the original unless explicitly asked to change the garage door. "
        f"The garage roof line and trim must be identical. "
        f"\n\nFRONT DOOR — PRESERVATION REQUIRED UNLESS EXPLICITLY ASKED TO CHANGE: "
        f"The front door must be in the exact same position, the exact same size, and the exact same style as the original unless explicitly asked to change it. "
        f"The door surround, transom, sidelights, and hardware must be identical unless explicitly asked to change them. "
        f"\n\nFOUNDATION AND STONEWORK: "
        f"The foundation, stone veneer, brick, or any masonry at the base of the house must be completely unchanged. "
        f"The steps, walkway, and any hardscaping must be identical. "
        f"The driveway shape, color, and texture must be identical. "
        f"\n\nLANDSCAPING AND ENVIRONMENT — ZERO TOLERANCE FOR CHANGES: "
        f"Every single tree, bush, shrub, plant, and flower must be in the exact same position with the exact same size and color. "
        f"The lawn must be identical in color, texture, and shape. "
        f"The sky must be identical including all clouds, blue tones, and lighting. "
        f"The shadows on the ground and on the house must fall in exactly the same direction and intensity. "
        f"The time of day and lighting conditions must be identical. "
        f"\n\nSCALE, PERSPECTIVE, AND FRAMING — ABSOLUTE PRESERVATION REQUIRED: "
        f"The house must occupy exactly the same portion of the frame as in the original. "
        f"Do not zoom in. Do not zoom out. Do not pan left or right. Do not tilt the camera angle. "
        f"Every architectural element must be exactly the same size relative to the image dimensions as in the original photo. "
        f"The vanishing point and perspective lines must be identical. "
        f"The horizon line must be in the exact same position. "
        f"\n\nDECORATIVE ELEMENTS: "
        f"The house number must be identical. "
        f"All light fixtures, sconces, and exterior lighting must be identical unless explicitly asked to change them. "
        f"The mailbox, address placard, security cameras, and any other accessories must be identical. "
        f"All window shutters must be identical unless explicitly asked to change them. "
        f"All trim, fascia, soffit, and gutters must be identical in color and style unless explicitly asked to change them. "
        f"\n\nFINAL MANDATORY QUALITY VERIFICATION: "
        f"Before producing your output, perform these verification checks: "
        f"CHECK 1 — Roofline: Does the roofline silhouette exactly match the original? Are all peaks, gables, and dormers in the same positions? "
        f"CHECK 2 — Windows: Are all windows present, in the same positions, and with the same number of panes? "
        f"CHECK 3 — Scale: Is the house the same size in the frame? Is the perspective identical? "
        f"CHECK 4 — Changes: Have ONLY the explicitly requested elements been changed? "
        f"CHECK 5 — Environment: Are the lawn, trees, sky, and driveway completely unchanged? "
        f"CHECK 6 — Photorealism: Does the result look like a professional architectural retouching job with realistic materials, lighting, and shadows? "
        f"If any of these checks fail, correct the output before returning it. "
        f"The final result must look like the original photograph with only the requested surfaces professionally repainted by a master retoucher."
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
    st.session_state.setdefault("show_before_after", False)
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("uploaded_sig", None)
    st.session_state.setdefault("last_batch_ids", [])
    st.session_state.setdefault("_var_display", [])
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
        anchored[f"{element}_texture"] = "Keep as is"
        anchored[f"{element}_custom_color"] = ""
        anchored[f"{element}_price"] = 0.0
        anchored[f"{element}_note"] = ""
    # Also anchor widget keys for any saved custom element tabs.
    for element in st.session_state.get("saved_custom_elements", []):
        anchored[f"{element}_color"] = "Keep as is"
        anchored[f"{element}_texture"] = "Keep as is"
        anchored[f"{element}_custom_color"] = ""
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
    if pending.get("color"):
        st.session_state[f"{element}_color"] = pending["color"]
    if pending.get("style"):
        st.session_state[f"{element}_texture"] = pending["style"]
    st.session_state["active_element"] = element


def build_edits_from_state():
    """Construct the edit_history list from the current per-element selections,
    skipping any element where both color and style are 'Keep as is'.
    Also includes saved custom element tabs and the freeform 'Something else?' entry."""
    edits = []
    all_elements = ELEMENTS + list(st.session_state.get("saved_custom_elements", []))
    for element in all_elements:
        raw_color = st.session_state.get(f"{element}_color", "Keep as is")
        texture = st.session_state.get(f"{element}_texture", "Keep as is")
        if raw_color == "Keep as is" and texture == "Keep as is":
            continue
        # Resolve "Custom" color to the typed value
        if raw_color == "Custom":
            color = (st.session_state.get(f"{element}_custom_color") or "").strip() or "custom color"
        else:
            color = raw_color
        custom_texture_desc = ""
        if texture == "Custom":
            custom_texture_desc = (st.session_state.get(f"{element}_custom_texture") or "").strip()
        edits.append({
            "id": str(uuid.uuid4()),
            "element": element,
            "color": color,
            "style": texture,         # texture stored in "style" field for describe_edit() compat
            "custom_color": "",
            "custom_style": custom_texture_desc,
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
    """Build edits from state, show the spinner in the image placeholder, call
    GPT-image-1, then replace the spinner with the result — all in one pass.

    _image_placeholder is created in main() before render_sidebar() runs so this
    function can reach it. Streamlit flushes each placeholder.markdown() call to
    the browser immediately via WebSocket, so the spinner appears before the
    blocking edit_image() call begins.
    """
    if not st.session_state.original_image_bytes:
        st.sidebar.error("Upload a house photo first.")
        return
    edits = build_edits_from_state()
    customs = st.session_state.custom_instructions
    if not edits and not customs:
        st.sidebar.warning("Select at least one change before generating.")
        return
    try:
        if _image_placeholder is not None:
            _image_placeholder.markdown(_SPINNER_HTML, unsafe_allow_html=True)
        _, image_bytes = edit_image(
            st.session_state.original_image_bytes, edits, customs
        )
        st.session_state.current_image_bytes = image_bytes
        st.session_state.edit_history = edits
        count = len(st.session_state.variations) + 1
        add_variation(f"Design {count}", image_bytes, edits, customs)
        st.session_state.last_batch_ids = []
        if _image_placeholder is not None:
            _image_placeholder.image(image_bytes, use_container_width=True)
        st.sidebar.success("Preview generated.")
    except Exception as exc:  # noqa: BLE001
        if _image_placeholder is not None:
            _image_placeholder.image(
                st.session_state.current_image_bytes, use_container_width=True
            )
        st.error(f"Generation failed: {exc}")


# --------------------------------------------------------------------------- #
# Sidebar sections (rendered inside the option-menu dispatch)
# --------------------------------------------------------------------------- #

def _parse_hex(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return 136, 136, 136


def _img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@st.cache_data
def generate_texture_previews() -> dict:
    """Generate 120x80 grayscale texture previews as base64 PNG strings. Cached once."""
    W, H = 120, 80
    rng = random.Random(42)  # fixed seed for deterministic output
    out = {}

    # Brick: alternating rows of rectangles offset every other row
    img = Image.new("RGB", (W, H), (100, 100, 100))
    draw = ImageDraw.Draw(img)
    bh, bw, m = 14, 30, 2
    for row in range(H // bh + 2):
        y = row * bh
        ox = (bw // 2) if row % 2 else 0
        x = -ox
        while x < W:
            c = rng.randint(82, 118)
            draw.rectangle([x + m, y + m, x + bw - m - 1, y + bh - m - 1],
                           fill=(c, c, c))
            x += bw
    out["Brick"] = _img_to_b64(img)

    # Stucco: base fill + many small random dots/dashes
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    for _ in range(800):
        x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
        c = rng.randint(65, 148)
        r = rng.randint(1, 3)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(c, c, c))
    out["Stucco"] = _img_to_b64(img)

    # Wood Panels: vertical stripes with subtle color variation + dark seam
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    pw_cycle = [18, 20, 17, 19, 18, 21, 17]
    x = 0
    for pw in pw_cycle * 4:
        if x >= W:
            break
        c = rng.randint(85, 122)
        draw.rectangle([x, 0, x + pw - 2, H - 1], fill=(c, c, c))
        draw.line([x + pw - 1, 0, x + pw - 1, H - 1], fill=(48, 48, 48), width=1)
        x += pw
    out["Wood Panels"] = _img_to_b64(img)

    # Cedar Shingles: overlapping horizontal trapezoids
    img = Image.new("RGB", (W, H), (92, 92, 92))
    draw = ImageDraw.Draw(img)
    sh = 16
    for row in range(H // sh + 2):
        y_top = row * sh
        y_bot = y_top + sh
        ox = 12 if row % 2 else 0
        sx = -22 + ox
        while sx < W + 22:
            c = rng.randint(78, 122)
            pts = [(sx + 2, y_top), (sx + 20, y_top),
                   (sx + 22, y_bot), (sx, y_bot)]
            draw.polygon(pts, fill=(c, c, c))
            draw.line([(sx, y_bot), (sx + 22, y_bot)],
                      fill=(48, 48, 48), width=1)
            sx += 22
    out["Cedar Shingles"] = _img_to_b64(img)

    # Board and Batten: wide vertical boards with narrow battens
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    x = 0
    while x < W:
        c = rng.randint(88, 122)
        draw.rectangle([x, 0, x + 19, H - 1], fill=(c, c, c))
        x += 20
        if x < W:
            draw.rectangle([x, 0, x + 3, H - 1], fill=(55, 55, 55))
            x += 4
    out["Board and Batten"] = _img_to_b64(img)

    # Stone Veneer: irregular polygons
    img = Image.new("RGB", (W, H), (88, 88, 88))
    draw = ImageDraw.Draw(img)
    for _ in range(35):
        cx, cy = rng.randint(8, W - 8), rng.randint(6, H - 6)
        n = rng.randint(5, 8)
        pts = []
        for i in range(n):
            angle = 2 * math.pi * i / n + rng.uniform(-0.4, 0.4)
            r = rng.randint(7, 16)
            pts.append((int(cx + r * math.cos(angle)),
                        int(cy + r * math.sin(angle))))
        c = rng.randint(72, 128)
        draw.polygon(pts, fill=(c, c, c), outline=(45, 45, 45))
    out["Stone Veneer"] = _img_to_b64(img)

    # Vinyl Lap: clean horizontal bands with subtle shadow/highlight lines
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    lh = 12
    for row in range(H // lh + 2):
        y = row * lh
        c = 95 + (row % 2) * 18
        draw.rectangle([0, y, W - 1, y + lh - 2], fill=(c, c, c))
        draw.line([0, y + lh - 1, W - 1, y + lh - 1], fill=(55, 55, 55), width=1)
        draw.line([0, y, W - 1, y], fill=(138, 138, 138), width=1)
    out["Vinyl Lap"] = _img_to_b64(img)

    # Metal Panel: horizontal panels with highlight at top and shadow at bottom
    img = Image.new("RGB", (W, H), (112, 112, 112))
    draw = ImageDraw.Draw(img)
    ph = 20
    for row in range(H // ph + 2):
        y = row * ph
        c = 102 + (row % 2) * 12
        draw.rectangle([0, y + 2, W - 1, y + ph - 2], fill=(c, c, c))
        draw.line([0, y, W - 1, y], fill=(155, 155, 155), width=1)
        draw.line([0, y + 1, W - 1, y + 1], fill=(142, 142, 142), width=1)
        draw.line([0, y + ph - 1, W - 1, y + ph - 1], fill=(65, 65, 65), width=1)
    out["Metal Panel"] = _img_to_b64(img)

    # ---- Roof textures -------------------------------------------------------

    # Asphalt Shingles: wide offset rows like cedar shingles but chunkier
    img = Image.new("RGB", (W, H), (75, 75, 75))
    draw = ImageDraw.Draw(img)
    sh = 18
    for row in range(H // sh + 2):
        y_top, y_bot = row * sh, row * sh + sh
        ox = 20 if row % 2 else 0
        sx = -40 + ox
        while sx < W + 40:
            c = rng.randint(60, 95)
            pts = [(sx + 2, y_top), (sx + 38, y_top),
                   (sx + 40, y_bot), (sx, y_bot)]
            draw.polygon(pts, fill=(c, c, c))
            draw.line([(sx, y_bot), (sx + 40, y_bot)], fill=(35, 35, 35), width=1)
            sx += 40
    out["Asphalt Shingles"] = _img_to_b64(img)

    # Slate Tiles: regular grid of rectangular tiles offset every other row
    img = Image.new("RGB", (W, H), (80, 80, 80))
    draw = ImageDraw.Draw(img)
    tw, th, tm = 28, 16, 2
    for row in range(H // th + 2):
        y = row * th
        ox = (tw // 2) if row % 2 else 0
        x = -ox
        while x < W:
            c = rng.randint(65, 100)
            draw.rectangle([x + tm, y + tm, x + tw - tm, y + th - tm], fill=(c, c, c))
            x += tw
    out["Slate Tiles"] = _img_to_b64(img)

    # Clay Tiles: rows of overlapping arc/dome shapes
    img = Image.new("RGB", (W, H), (95, 95, 95))
    draw = ImageDraw.Draw(img)
    tw2, th2 = 20, 22
    for row in range(H // th2 + 2):
        y = row * th2
        ox = (tw2 // 2) if row % 2 else 0
        x = -tw2 + ox
        while x < W + tw2:
            c = rng.randint(80, 118)
            # dome: filled ellipse at top, rectangle body below
            draw.ellipse([x + 2, y, x + tw2 - 2, y + th2 // 2 + 4], fill=(c, c, c))
            draw.rectangle([x + 2, y + th2 // 4, x + tw2 - 2, y + th2 - 2], fill=(max(0, c - 15), max(0, c - 15), max(0, c - 15)))
            x += tw2
        draw.line([0, y + th2 - 1, W, y + th2 - 1], fill=(45, 45, 45), width=1)
    out["Clay Tiles"] = _img_to_b64(img)

    # Metal Standing Seam: vertical seams with flat panel faces
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    sw = 16
    x = 0
    while x < W:
        c = rng.randint(95, 122)
        draw.rectangle([x, 0, x + sw - 3, H - 1], fill=(c, c, c))
        draw.rectangle([x + sw - 2, 0, x + sw - 1, H - 1], fill=(55, 55, 55))
        draw.line([x + sw - 3, 0, x + sw - 3, H - 1], fill=(148, 148, 148), width=1)
        x += sw
    out["Metal Standing Seam"] = _img_to_b64(img)

    # Wood Shake: irregular cedar shingles with rougher edges
    img = Image.new("RGB", (W, H), (88, 88, 88))
    draw = ImageDraw.Draw(img)
    sh2 = 14
    for row in range(H // sh2 + 2):
        y_top, y_bot = row * sh2, row * sh2 + sh2
        ox = rng.randint(0, 14) if row % 2 else 0
        sx = -28 + ox
        while sx < W + 28:
            c = rng.randint(70, 112)
            w_var = rng.randint(22, 32)
            pts = [(sx + 1, y_top), (sx + w_var - 1, y_top),
                   (sx + w_var + rng.randint(-2, 2), y_bot),
                   (sx + rng.randint(-2, 2), y_bot)]
            draw.polygon(pts, fill=(c, c, c))
            draw.line([(sx, y_bot), (sx + w_var, y_bot)], fill=(42, 42, 42), width=1)
            sx += w_var
    out["Wood Shake"] = _img_to_b64(img)

    # Copper: smooth metal panels (slightly lighter, more uniform than Metal Panel)
    img = Image.new("RGB", (W, H), (118, 118, 118))
    draw = ImageDraw.Draw(img)
    ph2 = 24
    for row in range(H // ph2 + 2):
        y = row * ph2
        c = 110 + (row % 2) * 10
        draw.rectangle([0, y + 1, W - 1, y + ph2 - 2], fill=(c, c, c))
        draw.line([0, y, W - 1, y], fill=(162, 162, 162), width=2)
        draw.line([0, y + ph2 - 1, W - 1, y + ph2 - 1], fill=(72, 72, 72), width=1)
    out["Copper"] = _img_to_b64(img)

    # Flat Membrane: nearly plain with subtle noise texture
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    for _ in range(200):
        x2, y2 = rng.randint(0, W - 1), rng.randint(0, H - 1)
        c = rng.randint(95, 115)
        draw.point((x2, y2), fill=(c, c, c))
    out["Flat Membrane"] = _img_to_b64(img)

    # ---- Front Door textures -------------------------------------------------

    # Solid Wood: wide vertical grain planks
    img = Image.new("RGB", (W, H), (102, 102, 102))
    draw = ImageDraw.Draw(img)
    pw2 = 24
    x = 0
    while x < W:
        c = rng.randint(82, 118)
        draw.rectangle([x, 0, x + pw2 - 2, H - 1], fill=(c, c, c))
        for grain_y in range(0, H, rng.randint(8, 16)):
            draw.line([x, grain_y, x + pw2 - 2, grain_y + rng.randint(-2, 2)],
                      fill=(max(0, c - 12), max(0, c - 12), max(0, c - 12)), width=1)
        draw.line([x + pw2 - 1, 0, x + pw2 - 1, H - 1], fill=(45, 45, 45), width=1)
        x += pw2
    out["Solid Wood"] = _img_to_b64(img)

    # Glass Panels: grid of light rectangles with frame
    img = Image.new("RGB", (W, H), (65, 65, 65))
    draw = ImageDraw.Draw(img)
    cols_g, rows_g = 3, 4
    cw = (W - 10) // cols_g
    ch = (H - 10) // rows_g
    for gy in range(rows_g):
        for gx in range(cols_g):
            x1 = 5 + gx * cw + 2
            y1 = 5 + gy * ch + 2
            draw.rectangle([x1, y1, x1 + cw - 4, y1 + ch - 4], fill=(145, 145, 145))
            draw.line([x1 + 1, y1 + 1, x1 + cw - 5, y1 + 1], fill=(175, 175, 175), width=1)
    out["Glass Panels"] = _img_to_b64(img)

    # Craftsman Style: wide top rail + horizontal divider + vertical bottom panels
    img = Image.new("RGB", (W, H), (85, 85, 85))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, W - 4, 22], fill=(105, 105, 105))   # top rail
    draw.rectangle([4, 22, W - 4, 26], fill=(50, 50, 50))      # divider
    for gx2 in range(3):
        x1 = 4 + gx2 * ((W - 8) // 3) + 2
        draw.rectangle([x1, 26, x1 + (W - 8) // 3 - 4, H - 4], fill=(98, 98, 98))
    out["Craftsman Style"] = _img_to_b64(img)

    # Arched: plain panel with arch outline at top
    img = Image.new("RGB", (W, H), (95, 95, 95))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, H // 3, W - 6, H - 6], fill=(108, 108, 108))
    draw.arc([6, 6, W - 6, H // 3 * 2], start=0, end=180, fill=(55, 55, 55), width=3)
    out["Arched"] = _img_to_b64(img)

    # Modern Flat: smooth solid with subtle vertical centerline
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    draw.line([W // 2, 0, W // 2, H], fill=(78, 78, 78), width=2)
    draw.rectangle([4, 4, W // 2 - 3, H - 4], fill=(110, 110, 110))
    draw.rectangle([W // 2 + 2, 4, W - 4, H - 4], fill=(110, 110, 110))
    out["Modern Flat"] = _img_to_b64(img)

    # French Doors: grid with vertical center divide and cross panels
    img = Image.new("RGB", (W, H), (72, 72, 72))
    draw = ImageDraw.Draw(img)
    draw.line([W // 2, 0, W // 2, H], fill=(50, 50, 50), width=3)
    for gy3 in range(3):
        y1 = 4 + gy3 * ((H - 8) // 3)
        for gx3 in range(2):
            x1 = 4 + gx3 * (W // 2)
            draw.rectangle([x1 + 3, y1 + 2, x1 + W // 2 - 6, y1 + (H - 8) // 3 - 3],
                           fill=(138, 138, 138))
    out["French Doors"] = _img_to_b64(img)

    # Steel: smooth metal with horizontal ribs
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    for rib_y in range(0, H, 10):
        draw.line([0, rib_y, W, rib_y], fill=(125, 125, 125), width=1)
        draw.line([0, rib_y + 1, W, rib_y + 1], fill=(88, 88, 88), width=1)
    out["Steel"] = _img_to_b64(img)

    # Fiberglass: subtle horizontal wood-grain-like lines
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    for grain_y2 in range(0, H, rng.randint(3, 6)):
        c = rng.randint(95, 115)
        draw.line([0, grain_y2, W, grain_y2 + rng.randint(-1, 1)], fill=(c, c, c), width=1)
    out["Fiberglass"] = _img_to_b64(img)

    # ---- Shutter textures ----------------------------------------------------

    # Louvered: angled horizontal slats
    img = Image.new("RGB", (W, H), (88, 88, 88))
    draw = ImageDraw.Draw(img)
    lh2 = 10
    for row2 in range(H // lh2 + 2):
        y = row2 * lh2
        c = 95 + (row2 % 2) * 15
        draw.polygon([(0, y + 3), (W, y), (W, y + lh2 - 2), (0, y + lh2)],
                     fill=(c, c, c))
        draw.line([0, y + lh2, W, y + lh2 - 3], fill=(45, 45, 45), width=1)
    out["Louvered"] = _img_to_b64(img)

    # Raised Panel: outer frame with inset raised rectangle
    img = Image.new("RGB", (W, H), (90, 90, 90))
    draw = ImageDraw.Draw(img)
    # top panel
    draw.rectangle([4, 4, W - 4, H // 2 - 2], fill=(105, 105, 105))
    draw.rectangle([8, 8, W - 8, H // 2 - 6], fill=(115, 115, 115))
    # bottom panel
    draw.rectangle([4, H // 2 + 2, W - 4, H - 4], fill=(105, 105, 105))
    draw.rectangle([8, H // 2 + 6, W - 8, H - 8], fill=(115, 115, 115))
    out["Raised Panel"] = _img_to_b64(img)

    # Flat Panel: plain flat with subtle border shadow
    img = Image.new("RGB", (W, H), (100, 100, 100))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, W - 4, H - 4], fill=(108, 108, 108))
    draw.rectangle([4, 4, W - 4, 5], fill=(125, 125, 125))
    draw.rectangle([4, H - 5, W - 4, H - 4], fill=(65, 65, 65))
    out["Flat Panel"] = _img_to_b64(img)

    # Bahama Style: diagonal angled slats (top-hinged style)
    img = Image.new("RGB", (W, H), (80, 80, 80))
    draw = ImageDraw.Draw(img)
    for i2 in range(-H, H + H, 12):
        c = rng.randint(85, 118)
        draw.polygon([(0, i2), (W, i2 - 20), (W, i2 - 10), (0, i2 + 10)],
                     fill=(c, c, c))
        draw.line([(0, i2 + 10), (W, i2 - 10)], fill=(45, 45, 45), width=1)
    out["Bahama Style"] = _img_to_b64(img)

    # Colonial: multiple raised sub-panels in a column
    img = Image.new("RGB", (W, H), (88, 88, 88))
    draw = ImageDraw.Draw(img)
    panel_h = (H - 8) // 3
    for pi in range(3):
        py = 4 + pi * panel_h
        draw.rectangle([4, py, W - 4, py + panel_h - 2], fill=(102, 102, 102))
        draw.rectangle([8, py + 4, W - 8, py + panel_h - 6], fill=(112, 112, 112))
    out["Colonial"] = _img_to_b64(img)

    # ---- Garage Door textures ------------------------------------------------

    # Carriage Style: wood plank background with X brace overlay
    img = Image.new("RGB", (W, H), (95, 95, 95))
    draw = ImageDraw.Draw(img)
    plank_w = 15
    x = 0
    while x < W:
        c = rng.randint(82, 112)
        draw.rectangle([x, 0, x + plank_w - 2, H - 1], fill=(c, c, c))
        x += plank_w
    draw.line([0, 0, W, H], fill=(55, 55, 55), width=3)
    draw.line([W, 0, 0, H], fill=(55, 55, 55), width=3)
    out["Carriage Style"] = _img_to_b64(img)

    # Modern Flat (Garage): clean horizontal bands
    img = Image.new("RGB", (W, H), (112, 112, 112))
    draw = ImageDraw.Draw(img)
    band_h = H // 4
    for bi in range(4):
        y = bi * band_h
        c = 105 + (bi % 2) * 12
        draw.rectangle([0, y, W - 1, y + band_h - 2], fill=(c, c, c))
        draw.line([0, y + band_h - 1, W - 1, y + band_h - 1], fill=(60, 60, 60), width=1)
    out["Modern Flat"] = _img_to_b64(img)

    # Full Glass: grid of light panes with dark frame
    img = Image.new("RGB", (W, H), (55, 55, 55))
    draw = ImageDraw.Draw(img)
    cols_gl, rows_gl = 4, 3
    cw2 = (W - 10) // cols_gl
    ch2 = (H - 8) // rows_gl
    for gy4 in range(rows_gl):
        for gx4 in range(cols_gl):
            x1 = 5 + gx4 * cw2 + 2
            y1 = 4 + gy4 * ch2 + 2
            draw.rectangle([x1, y1, x1 + cw2 - 4, y1 + ch2 - 4], fill=(155, 155, 155))
            draw.line([x1, y1, x1 + cw2 - 4, y1], fill=(175, 175, 175), width=1)
    out["Full Glass"] = _img_to_b64(img)

    # Wood Plank: horizontal planks (same idea as Wood Panels but rotated)
    img = Image.new("RGB", (W, H), (100, 100, 100))
    draw = ImageDraw.Draw(img)
    plank_h2 = 14
    y = 0
    while y < H:
        c = rng.randint(82, 118)
        draw.rectangle([0, y, W - 1, y + plank_h2 - 2], fill=(c, c, c))
        draw.line([0, y + plank_h2 - 1, W - 1, y + plank_h2 - 1], fill=(45, 45, 45), width=1)
        draw.line([0, y, W - 1, y], fill=(128, 128, 128), width=1)
        y += plank_h2
    out["Wood Plank"] = _img_to_b64(img)

    # Flush Panel: subtle horizontal seams only, very clean
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    seam_h = H // 4
    for si in range(4):
        y = si * seam_h
        draw.rectangle([0, y, W - 1, y + seam_h - 2], fill=(108 + (si % 2) * 4, 108 + (si % 2) * 4, 108 + (si % 2) * 4))
        draw.line([0, y + seam_h - 1, W - 1, y + seam_h - 1], fill=(75, 75, 75), width=1)
        draw.line([0, y, W - 1, y], fill=(130, 130, 130), width=1)
    out["Flush Panel"] = _img_to_b64(img)

    # ---- Gables-specific textures --------------------------------------------

    # Smooth Paint: uniform flat fill with very faint noise
    img = Image.new("RGB", (W, H), (108, 108, 108))
    draw = ImageDraw.Draw(img)
    for _ in range(120):
        x2, y2 = rng.randint(0, W - 1), rng.randint(0, H - 1)
        c = rng.randint(102, 114)
        draw.point((x2, y2), fill=(c, c, c))
    out["Smooth Paint"] = _img_to_b64(img)

    # Decorative Trim: horizontal bands with small raised bead detail
    img = Image.new("RGB", (W, H), (95, 95, 95))
    draw = ImageDraw.Draw(img)
    for iy in range(0, H, 16):
        draw.rectangle([0, iy + 2, W - 1, iy + 12], fill=(108, 108, 108))
        draw.line([0, iy + 2, W - 1, iy + 2], fill=(148, 148, 148), width=1)
        draw.line([0, iy + 3, W - 1, iy + 3], fill=(128, 128, 128), width=1)
        draw.line([0, iy + 11, W - 1, iy + 11], fill=(65, 65, 65), width=1)
        draw.line([0, iy + 12, W - 1, iy + 12], fill=(50, 50, 50), width=1)
    out["Decorative Trim"] = _img_to_b64(img)

    # Match Siding: vertical boards (reuses Board and Batten pattern, lighter fill)
    img = Image.new("RGB", (W, H), (105, 105, 105))
    draw = ImageDraw.Draw(img)
    x = 0
    while x < W:
        c = rng.randint(90, 120)
        draw.rectangle([x, 0, x + 18, H - 1], fill=(c, c, c))
        draw.line([x + 18, 0, x + 18, H - 1], fill=(55, 55, 55), width=1)
        x += 19
    out["Match Siding"] = _img_to_b64(img)

    return out


@st.cache_data
def tint_texture_preview(b64_gray: str, hex_color: str) -> str:
    """Blend a grayscale texture with a solid color overlay at 40% opacity."""
    img = Image.open(io.BytesIO(base64.b64decode(b64_gray))).convert("RGBA")
    r, g, b = _parse_hex(hex_color)
    overlay = Image.new("RGBA", img.size, (r, g, b, int(255 * 0.4)))
    return _img_to_b64(Image.alpha_composite(img, overlay))


def _render_element_picker(element):
    """Render the two-section color + texture picker for an element.
    All selections are stored immediately in session_state on click."""
    sel_color = st.session_state.get(f"{element}_color", "Keep as is")
    sel_texture = st.session_state.get(f"{element}_texture", "Keep as is")
    custom_hex = st.session_state.get(f"{element}_custom_color", "#c9a84c")
    color_hex = (
        custom_hex if sel_color == "Custom"
        else next((h for n, h in PICKER_COLORS if n == sel_color), "#888888")
    )

    # ---- Section label styles -----------------------------------------------
    _SEC = ("<div style='color:#888;font-size:10px;font-weight:600;"
            "letter-spacing:1px;margin:10px 0 6px;'>")

    _ck_a = sel_color == "Keep as is"
    _kt_a = sel_texture == "Keep as is"
    # Sanitised element name safe for use in CSS class names / button keys.
    _el_safe = element.replace(" ", "_")

    # ---- COLOR section — st.button() circles + rainbow Custom wheel ----------
    st.markdown(f"{_SEC}COLOR</div>", unsafe_allow_html=True)

    def _color_circle(col, cname, chex):
        is_sel = sel_color == cname
        border = "#c9a84c" if is_sel else "#2a2a2a"
        shadow = "0 0 8px rgba(201,168,76,0.55)" if is_sel else "none"
        css = [
            f"button {{ background-color:{chex} !important;"
            f" border:3px solid {border} !important;"
            f" border-radius:50% !important;"
            f" width:44px !important; height:44px !important;"
            f" min-width:44px !important; min-height:0 !important;"
            f" padding:0 !important; box-shadow:{shadow} !important;"
            f" outline:none !important;"
            f" display:block !important; margin:0 auto !important; }}",
            "button:hover { border-color:#c9a84c !important; }",
            "button:focus { outline:none !important; box-shadow:none !important; }",
            "button:focus-visible { outline:none !important; box-shadow:none !important; }",
            "button:active { outline:none !important; }",
            "button p { display:none !important; }",
        ]
        with col:
            with stylable_container(f"cpick_{element}_{cname}".replace(" ", "_"), css):
                if st.button(" ", key=f"cpbtn_{element}_{cname}"):
                    st.session_state[f"{element}_color"] = cname
                    st.rerun()

    # Row 1: first 5 colours
    cols1 = st.columns(5)
    for col, (cname, chex) in zip(cols1, PICKER_COLORS[:5]):
        _color_circle(col, cname, chex)

    # Row 2: remaining 4 colours + rainbow Custom wheel as the 5th slot
    cols2 = st.columns(5)
    for col, (cname, chex) in zip(cols2, PICKER_COLORS[5:]):
        _color_circle(col, cname, chex)

    # Rainbow Custom wheel — 5th slot of row 2
    is_custom = sel_color == "Custom"
    wheel_border = "#c9a84c" if is_custom else "#2a2a2a"
    wheel_shadow = "0 0 8px rgba(201,168,76,0.55)" if is_custom else "none"
    _wheel_css = [
        f"button {{ background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red)"
        f" !important; border:3px solid {wheel_border} !important;"
        f" border-radius:50% !important;"
        f" width:44px !important; height:44px !important;"
        f" min-width:44px !important; min-height:0 !important;"
        f" padding:0 !important; box-shadow:{wheel_shadow} !important;"
        f" outline:none !important;"
        f" display:block !important; margin:0 auto !important; }}",
        "button:hover { border-color:#c9a84c !important; }",
        "button:focus { outline:none !important; box-shadow:none !important; }",
        "button:focus-visible { outline:none !important; box-shadow:none !important; }",
        "button:active { outline:none !important; }",
        "button p { display:none !important; }",
    ]
    with cols2[4]:
        with stylable_container(f"cpick_{element}_Custom_wheel", _wheel_css):
            if st.button(" ", key=f"cpbtn_{element}_Custom"):
                st.session_state[f"{element}_color"] = "Custom"
                st.rerun()

    # Keep color — plain st.button (no stylable_container). Its dynamic gold/grey
    # state is styled by targeting the button's own key class st-key-cpkeep_btn_{element}.
    _ck_bg     = "#c9a84c" if _ck_a else "#2a2a2a"
    _ck_border = "#c9a84c" if _ck_a else "#555555"
    _ck_color  = "#000000" if _ck_a else "#aaaaaa"
    st.markdown(f"""
<style>
.st-key-cpkeep_btn_{_el_safe} button {{
    background:{_ck_bg} !important; border:1px solid {_ck_border} !important;
    color:{_ck_color} !important; font-size:11px !important; padding:4px 12px !important;
    border-radius:20px !important; min-height:0 !important; line-height:1.4 !important;
    margin-top:8px !important; width:auto !important;
}}
.st-key-cpkeep_btn_{_el_safe} button:hover {{
    background:#c9a84c !important; border-color:#c9a84c !important; color:#000000 !important;
}}
.st-key-cpkeep_btn_{_el_safe} button p {{
    color:inherit !important; font-size:11px !important; margin:0 !important;
}}
</style>
""", unsafe_allow_html=True)
    if st.button("✓ Keep color as is" if _ck_a else "Keep color as is",
                 key=f"cpkeep_btn_{_el_safe}"):
        st.session_state[f"{element}_color"] = "Keep as is"
        st.rerun()

    # When Custom is active show a color picker; changes update color_hex live
    if is_custom:
        _cp_value = st.session_state.get(f"{element}_custom_color") or "#ffffff"
        picked = st.color_picker(
            "Pick a custom color",
            value=_cp_value,
            key=f"colorpicker_{element}",
        )
        if picked != st.session_state.get(f"{element}_custom_color"):
            st.session_state[f"{element}_custom_color"] = picked
            st.rerun()

    # ---- TEXTURE section ----------------------------------------------------
    st.markdown(f"{_SEC}TEXTURE</div>", unsafe_allow_html=True)

    tex_previews = generate_texture_previews()
    _TEX_BTN_CSS = [
        "button { background:transparent !important; border:none !important;"
        " box-shadow:none !important; width:100% !important;"
        " padding:2px 0 !important; min-height:0 !important; }",
        "button:hover { color:#c9a84c !important; }",
        "button p { font-size:10px !important; margin:0 !important; }",
    ]

    # Element-specific texture list; fall back to Siding list for unknown elements
    _all_tex_slots = ELEMENT_TEXTURES.get(element, ELEMENT_TEXTURES["Siding"])

    _TEX_OVER_CSS = [
        "button { background:transparent !important; border:none !important;"
        " box-shadow:none !important; outline:none !important;"
        " width:100% !important;"
        " height:80px !important; min-height:80px !important;"
        " padding:0 !important; position:relative !important;"
        " z-index:2 !important; }",
        "button:hover { background:transparent !important; box-shadow:none !important; }",
        "button:focus { outline:none !important; box-shadow:none !important; }",
        "button:focus-visible { outline:none !important; box-shadow:none !important; }",
        "button:active { outline:none !important; box-shadow:none !important; }",
        "button p { display:none !important; }",
    ]

    st.markdown("<div style='padding:4px 2px;'>", unsafe_allow_html=True)
    for i in range(0, len(_all_tex_slots), 3):
        cols = st.columns([1, 1, 1], gap="small")
        for col, tex in zip(cols, _all_tex_slots[i:i + 3]):
            is_sel = sel_texture not in ("", "Keep as is") and sel_texture == tex
            border = "#c9a84c" if is_sel else "#2a2a2a"
            shadow = "0 0 8px rgba(201,168,76,0.55)" if is_sel else "none"
            safe = f"tpick_{element}_{tex}".replace(" ", "_")

            if tex == "Custom":
                # Dark card with dashed gold border — no image, just the label overlay
                with col:
                    with stylable_container(safe, _TEX_OVER_CSS):
                        if st.button(" ", key=f"tpbtn_{element}_{tex}",
                                     use_container_width=True):
                            st.session_state[f"{element}_texture"] = "Custom"
                            st.rerun()
                    st.markdown(
                        f"<div style='width:100%;height:80px;border-radius:8px;"
                        f"border:2px dashed {border};box-shadow:{shadow};"
                        f"overflow:hidden;box-sizing:border-box;"
                        f"margin-top:-84px;margin-bottom:8px;"
                        f"background:#1a1a1a;"
                        f"position:relative;z-index:1;display:flex;"
                        f"align-items:center;justify-content:center;'>"
                        f"<div style='position:absolute;bottom:0;left:0;width:100%;"
                        f"background:rgba(0,0,0,0.6);color:#c9a84c;font-size:11px;"
                        f"text-align:center;padding:3px 0;box-sizing:border-box;'>Custom</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                b64 = tint_texture_preview(tex_previews[tex], color_hex)
                with col:
                    with stylable_container(safe, _TEX_OVER_CSS):
                        if st.button(" ", key=f"tpbtn_{element}_{tex}",
                                     use_container_width=True):
                            st.session_state[f"{element}_texture"] = tex
                            st.rerun()
                    st.markdown(
                        f"<div style='width:100%;height:80px;border-radius:8px;"
                        f"border:2px solid {border};box-shadow:{shadow};"
                        f"overflow:hidden;box-sizing:border-box;"
                        f"margin-top:-84px;margin-bottom:8px;"
                        f"position:relative;z-index:1;"
                        f"display:flex;align-items:center;justify-content:center;'>"
                        f"<img src='data:image/png;base64,{b64}' "
                        f"style='width:100%;height:80px;object-fit:cover;"
                        f"object-position:center center;display:block;'/>"
                        f"<div style='position:absolute;bottom:0;left:0;width:100%;"
                        f"background:rgba(0,0,0,0.6);color:#ffffff;font-size:11px;"
                        f"text-align:center;padding:3px 0;box-sizing:border-box;'>{tex}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
    st.markdown("</div>", unsafe_allow_html=True)

    if sel_texture == "Custom":
        st.text_input(
            "Describe your texture",
            key=f"{element}_custom_texture",
            placeholder="e.g. smooth concrete, corrugated metal...",
        )

    # Keep texture — plain st.button styled by its own key class (matches keep color).
    _kt_bg     = "#c9a84c" if _kt_a else "#2a2a2a"
    _kt_border = "#c9a84c" if _kt_a else "#555555"
    _kt_color  = "#000000" if _kt_a else "#aaaaaa"
    st.markdown(f"""
<style>
.st-key-tpkeep_btn_{_el_safe} button {{
    background:{_kt_bg} !important; border:1px solid {_kt_border} !important;
    color:{_kt_color} !important; font-size:11px !important; padding:4px 12px !important;
    border-radius:20px !important; min-height:0 !important; line-height:1.4 !important;
    margin-top:0 !important; margin-bottom:8px !important; width:auto !important;
}}
.st-key-tpkeep_btn_{_el_safe} button:hover {{
    background:#c9a84c !important; border-color:#c9a84c !important; color:#000000 !important;
}}
.st-key-tpkeep_btn_{_el_safe} button p {{
    color:inherit !important; font-size:11px !important; margin:0 !important;
}}
</style>
""", unsafe_allow_html=True)
    if st.button("✓ Keep texture as is" if _kt_a else "Keep texture as is",
                 key=f"tpkeep_btn_{_el_safe}"):
        st.session_state[f"{element}_texture"] = "Keep as is"
        st.session_state.pop(f"{element}_custom_texture", None)
        st.rerun()


def sb_design():
    """Design panel: element tabs (built-in + Custom), a visual swatch grid for
    each element, freeform custom instructions, and the generate buttons."""
    all_elements_for_tabs = ELEMENTS + ["Custom"]

    st.markdown("<div class='sb-h'>Elements</div>", unsafe_allow_html=True)

    current = st.session_state.get("active_element", "Siding")
    if current not in all_elements_for_tabs:
        current = ELEMENTS[0]

    _EL_BTN_BASE = (
        " border:none !important; border-radius:8px !important;"
        " width:100% !important; padding:4px 2px !important;"
        " white-space:nowrap !important;"
        " overflow:hidden !important; text-overflow:ellipsis !important;"
        " min-height:32px !important; line-height:1.2 !important;"
        " box-sizing:border-box !important;"
    )
    # button p rule is a separate list entry so it stays scoped to this button.
    _EL_P = ("button p { text-align:center !important; font-size:13px !important;"
             " white-space:nowrap !important; margin:0 !important; }")
    _EL_ACTIVE_CSS = [
        f"button {{ background-color:#c9a84c !important; color:#000000 !important;"
        f" font-weight:700 !important;{_EL_BTN_BASE} }}",
        "button:hover { background-color:#c9a84c !important; color:#000000 !important; }",
        "button:focus { outline:none !important; box-shadow:none !important;"
        " border-radius:8px !important; }",
        "button:focus-visible { outline:none !important; box-shadow:none !important;"
        " border-radius:8px !important; }",
        "button:active { outline:none !important; box-shadow:none !important; }",
        _EL_P,
    ]
    _EL_INACTIVE_CSS = [
        f"button {{ background-color:#1e1e1e !important; color:#aaaaaa !important;"
        f" font-weight:500 !important;{_EL_BTN_BASE} }}",
        "button:hover { background-color:#252525 !important; color:#c9a84c !important; }",
        "button:focus { outline:none !important; box-shadow:none !important;"
        " border-radius:8px !important; }",
        "button:focus-visible { outline:none !important; box-shadow:none !important;"
        " border-radius:8px !important; }",
        "button:active { outline:none !important; box-shadow:none !important; }",
        _EL_P,
    ]

    def _el_button(col, el_name):
        is_active = current == el_name
        with col:
            with stylable_container(f"eltab_{el_name}", _EL_ACTIVE_CSS if is_active else _EL_INACTIVE_CSS):
                if st.button(el_name, key=f"eltab_btn_{el_name}", use_container_width=True):
                    # Reset texture if current selection isn't valid for the new element
                    valid_textures = ELEMENT_TEXTURES.get(el_name, [])
                    cur_tex = st.session_state.get(f"{el_name}_texture", "Keep as is")
                    if cur_tex not in valid_textures and cur_tex != "Keep as is":
                        st.session_state[f"{el_name}_texture"] = "Keep as is"
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

    # Row 1: Siding, Roof, Front Door
    for col, el_name in zip(st.columns(3), ["Siding", "Roof", "Front Door"]):
        _el_button(col, el_name)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    # Row 2: Shutters, Garage Door, Gables
    for col, el_name in zip(st.columns(3), ["Shutters", "Garage Door", "Gables"]):
        _el_button(col, el_name)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    # Row 3: Custom centered in the middle column
    c_left, c_mid, c_right = st.columns(3)
    _el_button(c_mid, "Custom")

    element = current

    if element == "Custom":
        # ---- Freeform custom element: two inputs, included automatically --- #
        st.markdown(
            "<div style='color:#fff;font-weight:600;margin:8px 0 4px;font-size:15px;'>"
            "Custom Element</div>",
            unsafe_allow_html=True,
        )
        st.text_input(
            "What element?", key="custom_element_text",
            placeholder="e.g. chimney, porch columns, walkway...",
        )
        st.text_input(
            "Describe the change", key="custom_element_description",
            placeholder="e.g. paint it black with a modern style",
        )
        st.caption("Filled-in custom changes are included automatically when you generate.")

    else:
        # ---- Color + texture picker --------------------------------------- #
        _render_element_picker(element)

        with st.expander("Add to Quote (optional)", expanded=False):
            st.session_state.setdefault(f"{element}_price", 0.0)
            st.session_state.setdefault(f"{element}_note", "")
            st.number_input("Estimated price ($)", min_value=0.0, step=100.0,
                            key=f"{element}_price")
            st.text_input("Note (material, brand, etc.)", key=f"{element}_note",
                          placeholder="optional")

    # ---- Custom instructions -------------------------------------------- #
    st.markdown("<div class='sb-h'>Add Something Custom</div>", unsafe_allow_html=True)
    custom_text = st.text_area(
        "Custom instruction", key="custom_instruction_input", height=80,
        placeholder="e.g. Add a lamppost on the left, add window boxes with flowers",
        label_visibility="collapsed",
    )
    _ADD_INSTR_CSS = [
        "button { background-color:#1a1a1a !important; color:#c9a84c !important;"
        " border:1px solid #3a3a3a !important; border-radius:8px !important;"
        " width:100% !important; padding:8px !important; }",
        "button:hover { border-color:#c9a84c !important; color:#c9a84c !important; }",
        "button p { color:#c9a84c !important; font-size:13px !important; margin:0 !important; }",
    ]
    with stylable_container("add_instr_btn", _ADD_INSTR_CSS):
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
    _GEN_PRIMARY_CSS = [
        "button { background-color:#c9a84c !important; color:#000000 !important;"
        " font-weight:700 !important; border:none !important; border-radius:8px !important;"
        " width:100% !important; padding:12px !important; }",
        "button:hover { background-color:#d8b85c !important; color:#000000 !important; }",
        "button p { color:#000000 !important; font-weight:700 !important; font-size:15px !important; margin:0 !important; }",
    ]
    _GEN_SECONDARY_CSS = [
        "button { background-color:#1a1a1a !important; color:#c9a84c !important;"
        " font-weight:600 !important; border:1px solid #3a3a3a !important; border-radius:8px !important;"
        " width:100% !important; padding:9px !important; margin-top:6px !important; }",
        "button:hover { border-color:#c9a84c !important; color:#c9a84c !important; }",
        "button p { color:#c9a84c !important; font-size:13px !important; margin:0 !important; }",
    ]
    with stylable_container("gen_preview_btn", _GEN_PRIMARY_CSS):
        if st.button("Generate Preview", use_container_width=True, key="gen_preview"):
            run_generate()

    with stylable_container("gen_var_btn", _GEN_SECONDARY_CSS):
        if st.button("Generate 3 Variations", use_container_width=True, key="gen_var"):
            _run_generate_variations()


def _run_generate_variations():
    """Find the first changed element and generate 3 texture variations.

    Uses _var_placeholder (set in main()) for progress bar and results so that
    all output appears in the main area, not the sidebar.
    """
    if not st.session_state.original_image_bytes:
        st.sidebar.error("Upload a house photo first.")
        return

    # Find first element with any non-default color OR texture selection.
    target = None
    for element in ELEMENTS:
        has_color = st.session_state.get(f"{element}_color", "Keep as is") not in ("", "Keep as is")
        has_texture = st.session_state.get(f"{element}_texture", "") not in ("", "Keep as is")
        if has_color or has_texture:
            target = element
            break
    if not target:
        st.sidebar.warning("Select a change on at least one element first.")
        return

    # Top 3 textures for the target element (skip Custom and Keep as is).
    tex_options = [t for t in ELEMENT_TEXTURES.get(target, ELEMENT_TEXTURES["Siding"])
                   if t not in ("Custom", "Keep as is")][:3]
    base_edits = build_edits_from_state()
    n = len(tex_options)

    # Show progress in the main area via _var_placeholder.
    container = _var_placeholder if _var_placeholder is not None else st
    progress_slot = container.empty() if _var_placeholder is not None else st.empty()
    progress_bar = progress_slot.progress(0, text=f"Generating variation 1 of {n}…")

    results = []
    for i, tex in enumerate(tex_options):
        temp_edit = {
            "id": str(uuid.uuid4()),
            "element": target,
            "color": st.session_state.get(f"{target}_color", "Keep as is"),
            "style": tex,
            "custom_color": st.session_state.get(f"{target}_custom_color", ""),
            "custom_style": "",
            "note": "",
            "price": 0.0,
            "selected": False,
        }
        temp_history = [e for e in base_edits if e.get("element") != target] + [temp_edit]
        try:
            _, image_bytes = edit_image(
                st.session_state.original_image_bytes, temp_history,
                st.session_state.custom_instructions,
            )
            results.append((image_bytes, tex))
        except Exception as exc:
            st.sidebar.error(f"Variation '{tex}' failed: {exc}")
        progress_bar.progress((i + 1) / n, text=f"Generated {i + 1} of {n}…")

    progress_slot.empty()

    batch = []
    for image_bytes, tex in results:
        var = add_variation(f"{target}: {tex}", image_bytes,
                            base_edits, st.session_state.custom_instructions)
        batch.append(var["id"])
    st.session_state.last_batch_ids = batch
    # Store lightweight display data so render_variation_cards() can render
    # without re-looking up variations by id on every rerun.
    st.session_state["_var_display"] = [
        {"label": f"Option {i + 1}", "name": f"{target}: {tex}", "image_bytes": img_b,
         "image_bytes_key": var_id}
        for i, ((img_b, tex), var_id) in enumerate(zip(results, batch))
    ]
    if results:
        st.rerun()


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
                for k in (f"{el}_color", f"{el}_texture", f"{el}_custom_color",
                          f"{el}_price", f"{el}_note")
            },
            "custom_element_state": {
                k: st.session_state.get(k)
                for el in saved_custom
                for k in (f"{el}_color", f"{el}_texture", f"{el}_custom_color",
                          f"{el}_price", f"{el}_note")
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
    _NAV_P = ("button p { text-align:left !important; width:100% !important;"
              " margin:0 !important; font-size:15px !important; }")
    # List form keeps button:hover / button p scoped to each nav container.
    _NAV_ACTIVE = [
        f"button {{ background-color:#c9a84c !important; color:#000000 !important;"
        f" font-weight:700 !important;{_NAV_BTN_BASE} }}",
        "button:hover { background-color:#c9a84c !important; color:#000000 !important; }",
        _NAV_P,
    ]
    _NAV_INACTIVE = [
        f"button {{ background-color:#1a1a1a !important; color:#aaaaaa !important;"
        f" font-weight:500 !important;{_NAV_BTN_BASE} }}",
        "button:hover { background-color:#c9a84c !important; color:#000000 !important; }",
        _NAV_P,
    ]

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
    """Minimal toolbar: just the Download button as a data-URI anchor."""
    img_b64 = base64.b64encode(st.session_state.current_image_bytes).decode()
    BTN = (
        "width:44px;height:44px;border-radius:50%;background:#1e1e1e;"
        "border:1px solid #c9a84c;cursor:pointer;"
        "display:flex;align-items:center;justify-content:center;"
        "transition:background .18s,box-shadow .18s;"
        "padding:0;box-sizing:border-box;text-decoration:none;"
    )
    HVR = (
        'onmouseover="this.style.background=\'rgba(201,168,76,0.10)\';" '
        'onmouseout="this.style.background=\'#1e1e1e\';"'
    )
    html = f"""
<div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:4px 0;">
  <a href="data:image/png;base64,{img_b64}" download="exterior_design.png"
     title="Download" style="{BTN}" {HVR}>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <path d="M12 3v12M6 11l6 6 6-6M4 20h16" stroke="#c9a84c" stroke-width="1.5"
            fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </a>
</div>
"""
    st.components.v1.html(html, height=70)


def render_hero_landing(file_uploader_key="hero_upload"):
    """Full-page hero shown before any image is uploaded."""
    # Title + subtitle — tight top padding so slider fits on screen
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&display=swap');
</style>
<div style="text-align:center;padding:10px 0 12px;">
  <div style="font-family:'Cormorant Garamond',serif;font-size:72px;font-weight:700;
              color:#c9a84c;letter-spacing:-0.5px;line-height:1.1;">
    Exterior Design Studio
  </div>
  <div style="font-family:'Inter',sans-serif;font-size:18px;color:#888888;
              margin-top:8px;font-weight:400;">
    Transform any home in seconds.
  </div>
</div>
""", unsafe_allow_html=True)

    # Before/after demo slider + chevron — all in one iframe to avoid extra gaps
    if _HERO_BEFORE_B64 and _HERO_AFTER_B64:
        height = int(900 * (667 / 1000))   # source images are 1000×667
        total_h = height + 80              # slider + caption + chevron + bounce travel + margin
        demo_html = f"""
<style>
@keyframes bounce-chevron {{
  0%, 100% {{ transform: translateY(0); opacity: 0.7; }}
  50%       {{ transform: translateY(6px); opacity: 1; }}
}}
.hero-chevron {{
  display: block;
  margin: 8px auto 20px;
  width: 24px; height: 14px;
  overflow: visible;
  animation: bounce-chevron 1.5s ease-in-out infinite;
}}
</style>
<div style="display:flex;flex-direction:column;align-items:center;width:100%;
            gap:0;overflow:visible;padding-bottom:4px;">
  <div style="position:relative;width:900px;max-width:96vw;height:{height}px;
              overflow:hidden;border-radius:14px;user-select:none;
              border:2px solid rgba(201,168,76,0.50);
              box-shadow:0 10px 32px rgba(0,0,0,0.6);" id="hero-wrap">
    <img src="data:image/jpeg;base64,{_HERO_BEFORE_B64}"
         style="position:absolute;top:0;left:0;width:900px;height:{height}px;
                object-fit:cover;" draggable="false"/>
    <div id="hero-after" style="position:absolute;top:0;left:0;width:50%;
         height:{height}px;overflow:hidden;">
      <img src="data:image/jpeg;base64,{_HERO_AFTER_B64}"
           style="width:900px;height:{height}px;object-fit:cover;" draggable="false"/>
    </div>
    <div id="hero-divider" style="position:absolute;top:0;left:50%;width:3px;
         height:{height}px;background:#c9a84c;cursor:ew-resize;
         box-shadow:0 0 12px rgba(201,168,76,0.9);transform:translateX(-50%);"></div>
    <div style="position:absolute;top:12px;left:14px;background:rgba(0,0,0,0.65);
         color:#fff;padding:3px 10px;border-radius:6px;
         font-family:Inter,sans-serif;font-size:11px;letter-spacing:1px;">BEFORE</div>
    <div style="position:absolute;top:12px;right:14px;background:rgba(201,168,76,0.90);
         color:#0f0f0f;padding:3px 10px;border-radius:6px;
         font-family:Inter,sans-serif;font-size:11px;letter-spacing:1px;
         font-weight:700;">AFTER</div>
  </div>
  <div style="text-align:center;color:#c9a84c;font-size:12px;
              font-family:Inter,sans-serif;margin-top:8px;margin-bottom:2px;">
    Drag the slider to see the transformation
  </div>
  <svg class="hero-chevron" viewBox="0 0 24 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <polyline points="2,2 12,12 22,2" stroke="#c9a84c" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round"
              transform="rotate(180 12 7)"/>
  </svg>
</div>
<script>
(function(){{
  const wrap     = document.getElementById('hero-wrap');
  const afterBox = document.getElementById('hero-after');
  const divider  = document.getElementById('hero-divider');
  let dragging = false;
  function setPos(clientX) {{
    const rect = wrap.getBoundingClientRect();
    let x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const pct = (x / rect.width) * 100;
    afterBox.style.width = pct + '%';
    divider.style.left   = pct + '%';
  }}
  divider.addEventListener('mousedown', (e) => {{ dragging = true; e.preventDefault(); }});
  window.addEventListener('mouseup',   () => dragging = false);
  window.addEventListener('mousemove', (e) => {{ if (dragging) setPos(e.clientX); }});
  wrap.addEventListener('click', (e) => setPos(e.clientX));
  wrap.addEventListener('touchstart', (e) => {{ dragging = true; setPos(e.touches[0].clientX); e.preventDefault(); }}, {{passive:false}});
  window.addEventListener('touchend',   () => dragging = false);
  window.addEventListener('touchmove',  (e) => {{ if (dragging) setPos(e.touches[0].clientX); }});
}})();
</script>
"""
        st.components.v1.html(demo_html, height=total_h)

    # Feature callouts row
    st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;gap:0;
            margin:14px auto 14px;max-width:480px;">
  <div style="flex:1;text-align:center;font-family:'Inter',sans-serif;
              font-size:13px;color:#c9a84c;font-weight:500;letter-spacing:0.4px;">
    Any house
  </div>
  <div style="width:1px;height:18px;background:rgba(201,168,76,0.35);flex-shrink:0;"></div>
  <div style="flex:1;text-align:center;font-family:'Inter',sans-serif;
              font-size:13px;color:#c9a84c;font-weight:500;letter-spacing:0.4px;">
    Any style
  </div>
  <div style="width:1px;height:18px;background:rgba(201,168,76,0.35);flex-shrink:0;"></div>
  <div style="flex:1;text-align:center;font-family:'Inter',sans-serif;
              font-size:13px;color:#c9a84c;font-weight:500;letter-spacing:0.4px;">
    In seconds
  </div>
</div>
""", unsafe_allow_html=True)

    # Upload heading + pulsing dropzone
    st.markdown("""
<div style="text-align:center;font-family:'Playfair Display',serif;font-size:16px;
            color:#c9a84c;margin-bottom:10px;font-weight:600;">
  Upload your house to get started
</div>
<style>
@keyframes pulse-border {
    0%   { border-color: rgba(201,168,76,0.3); }
    50%  { border-color: rgba(201,168,76,0.9); }
    100% { border-color: rgba(201,168,76,0.3); }
}
section[data-testid="stFileUploaderDropzone"] {
    border: 2px solid rgba(201,168,76,0.3) !important;
    border-radius: 14px !important;
    padding: 28px 20px !important;
    animation: pulse-border 2.4s ease-in-out infinite !important;
    background: rgba(201,168,76,0.04) !important;
}
section[data-testid="stFileUploaderDropzone"]:hover {
    animation: none !important;
    border-color: rgba(201,168,76,0.9) !important;
    background: rgba(201,168,76,0.07) !important;
}
</style>
""", unsafe_allow_html=True)

    _, upload_col, _ = st.columns([1, 2, 1])
    with upload_col:
        uploaded = st.file_uploader(
            "Upload a house photo",
            type=["jpg", "jpeg", "png"],
            key=file_uploader_key,
            label_visibility="collapsed",
        )

    return uploaded


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
    <div style="display:flex;justify-content:center;width:100%;">
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
    """Display the most recent batch of variations as image columns with Use This buttons."""
    display = st.session_state.get("_var_display", [])
    if not display:
        return

    st.markdown(
        "<div style='color:#c9a84c;font-family:\"Playfair Display\",serif;"
        "font-size:18px;font-weight:700;margin:24px 0 12px;'>Design Variations</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for col, item in zip(cols, display):
        with col:
            st.markdown(
                f"<div style='color:#ffffff;font-weight:600;font-size:14px;"
                f"margin-bottom:6px;text-align:center;'>{item['label']}</div>",
                unsafe_allow_html=True,
            )
            st.image(item["image_bytes"], use_container_width=True)
            st.markdown(
                f"<div style='color:#aaaaaa;font-size:11px;text-align:center;"
                f"margin-bottom:6px;'>{item['name']}</div>",
                unsafe_allow_html=True,
            )
            if st.button("Use This", key=f"use_var_{item['image_bytes_key']}",
                         use_container_width=True):
                st.session_state.current_image_bytes = item["image_bytes"]
                st.session_state["_var_display"] = []
                st.session_state.last_batch_ids = []
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
# Floating sidebar re-open button (injected into parent document)
# --------------------------------------------------------------------------- #
def render_sidebar_float_btn():
    """Inject a fixed pill button into the parent page that appears only when
    the Streamlit sidebar is collapsed, allowing the user to re-open it."""
    st.components.v1.html(
        """<script>
(function() {
    var doc = window.parent.document;
    var BTNID = 'eds-sidebar-float-btn';

    if (!doc.getElementById(BTNID)) {
        var btn = doc.createElement('div');
        btn.id = BTNID;
        btn.innerHTML = (
            '<span style="font-size:14px;line-height:1;margin-bottom:2px;">&#9654;</span>'
            + '<span style="font-size:10px;font-weight:700;letter-spacing:1.5px;">MENU</span>'
        );
        btn.style.cssText = [
            'position:fixed',
            'left:0',
            'top:50%',
            'transform:translateY(-50%)',
            'background:#1e1e1e',
            'color:#c9a84c',
            'border:1px solid #c9a84c',
            'border-left:none',
            'border-radius:0 20px 20px 0',
            'padding:14px 16px 14px 10px',
            'display:none',
            'flex-direction:column',
            'align-items:center',
            'gap:5px',
            'cursor:pointer',
            'z-index:99999',
            'font-family:Inter,sans-serif',
            'box-shadow:3px 0 12px rgba(0,0,0,0.6)',
            'transition:transform 0.15s ease,box-shadow 0.15s ease',
            'user-select:none',
        ].join(';');

        btn.addEventListener('mouseenter', function() {
            btn.style.transform = 'translateY(-50%) translateX(3px)';
            btn.style.boxShadow = '5px 0 16px rgba(201,168,76,0.35)';
        });
        btn.addEventListener('mouseleave', function() {
            btn.style.transform = 'translateY(-50%)';
            btn.style.boxShadow = '3px 0 12px rgba(0,0,0,0.6)';
        });
        btn.addEventListener('click', function() {
            var expandBtn = doc.querySelector('[data-testid="collapsedControl"]');
            if (expandBtn) expandBtn.click();
        });

        doc.body.appendChild(btn);
    }

    function syncVisibility() {
        var floatBtn = doc.getElementById(BTNID);
        if (!floatBtn) return;
        var collapsed = doc.querySelector('[data-testid="collapsedControl"]');
        floatBtn.style.display = collapsed ? 'flex' : 'none';
    }

    if (!window.__eds_sb_watcher) {
        window.__eds_sb_watcher = setInterval(syncVisibility, 250);
    }
    syncVisibility();
})();
        </script>""",
        height=0,
    )


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    """Application entry point: configure the page, inject the theme, initialise
    state, and render either the presentation view or the full studio."""
    st.set_page_config(page_title="Exterior Design Studio", layout="wide", initial_sidebar_state="expanded")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    init_state()
    apply_pending_preset()

    # ---- Hero landing (shown only before an image is uploaded) ------------ #
    if not st.session_state.original_image_bytes:
        hero_upload = render_hero_landing()
        if hero_upload is not None:
            data = hero_upload.getvalue()
            signature = (hero_upload.name, len(data))
            if st.session_state.uploaded_sig != signature:
                st.session_state.original_image_bytes = data
                st.session_state.current_image_bytes = data
                st.session_state.edit_history = []
                st.session_state.custom_instructions = []
                st.session_state.uploaded_sig = signature
                st.session_state.last_batch_ids = []
                st.session_state["_var_display"] = []
                st.rerun()
        return

    render_header()

    # ---- Image upload (shown only after a photo is already loaded) ------- #
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
            st.session_state["_var_display"] = []
            st.success("Photo loaded. Use the sidebar to design.")

    # ---- Image + toolbar ------------------------------------------------- #
    # The placeholder is created here — before render_sidebar() — so that
    # run_generate() (called from the sidebar's Generate button) can write the
    # spinner into it immediately, before the blocking edit_image() call.
    # The frame CSS is scoped to .st-key-hero_image_row to avoid leaking the
    # gold border/radius onto every first-column element in the sidebar.
    global _image_placeholder, _var_placeholder
    with st.container(key="hero_image_row"):
        st.markdown("""
<style>
.st-key-hero_image_row div[data-testid="stHorizontalBlock"] > div:first-child > div[data-testid="stVerticalBlock"] {
    background: #161616;
    border: 2px solid rgba(201,168,76,0.70);
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 10px 36px rgba(0,0,0,0.55);
    padding: 0;
}
.st-key-hero_image_row div[data-testid="stHorizontalBlock"] > div:first-child img {
    width: 100% !important;
    max-width: none !important;
    height: auto !important;
    border-radius: 18px;
    display: block;
}
</style>
""", unsafe_allow_html=True)
        img_col, tb_col = st.columns([13, 1])
        with img_col:
            _image_placeholder = st.empty()
            _image_placeholder.image(
                st.session_state.current_image_bytes, use_container_width=True
            )
        with tb_col:
            render_icon_toolbar()

    # Variations placeholder — created before render_sidebar() so that
    # _run_generate_variations() can write its progress bar here from the sidebar.
    _var_placeholder = st.empty()

    # Sidebar rendered AFTER the placeholders so sidebar callbacks can reach them.
    # Sidebar content always renders in the left panel regardless of call order.
    render_sidebar()
    render_sidebar_float_btn()

    # Render any variation cards stored from the last "Generate 3 Variations" run.
    render_variation_cards()

    # ---- Before/After toggle (only if a generation has happened) ----------- #
    _orig = st.session_state.original_image_bytes
    _curr = st.session_state.current_image_bytes
    _ba_generated = _orig is not None and _curr is not None and _curr != _orig
    if _ba_generated:
        _ba_active = st.session_state.get("show_before_after", False)
        _BA_CSS = [
            "button { background:#1e1e1e !important; color:#c9a84c !important;"
            " border:1px solid #c9a84c !important; border-radius:8px !important;"
            " padding:8px 20px !important; font-size:13px !important; }",
            "button:hover { background:rgba(201,168,76,0.1) !important; }",
            "button p { color:#c9a84c !important; font-size:13px !important; margin:0 !important; }",
        ]
        st.markdown("<br>", unsafe_allow_html=True)
        _, ba_col, _ = st.columns([1, 2, 1])
        with ba_col:
            with stylable_container("ba_toggle_btn", _BA_CSS):
                if st.button("⧉  Before / After", key="ba_toggle", use_container_width=True):
                    st.session_state["show_before_after"] = not _ba_active
                    st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # ---- Before/After slider --------------------------------------------- #
    if (st.session_state.get("show_before_after")
            and st.session_state.original_image_bytes
            and st.session_state.current_image_bytes):
        render_before_after_slider()

    # ---- Tabbed lower panels (manual session_state tabs) ----------------- #
    st.session_state.setdefault("active_bottom_tab", "history")

    _TABS = [
        ("history",  "Edit History"),
        ("quote",    "Quote"),
        ("compare",  "Compare"),
        ("timeline", "Design History"),
    ]

    # Inject CSS targeting st.container(key=f"btab_btn_{tid}") wrappers.
    # st.container(key="btab_btn_history") → class st-key-btab_btn_history (no double-prefix).
    _active_tid = st.session_state.get("active_bottom_tab", "history")
    st.markdown(f"""
<style>
.st-key-btab_btn_history button,
.st-key-btab_btn_quote button,
.st-key-btab_btn_compare button,
.st-key-btab_btn_timeline button {{
    border-radius: 8px 8px 0 0 !important;
    min-height: 36px !important; height: 36px !important;
    font-size: 13px !important; padding: 8px 4px !important;
    width: 100% !important; border: none !important;
    outline: none !important; box-sizing: border-box !important;
    background-color: #1e1e1e !important;
    color: #aaaaaa !important; font-weight: 500 !important;
}}
.st-key-btab_btn_history button:hover,
.st-key-btab_btn_quote button:hover,
.st-key-btab_btn_compare button:hover,
.st-key-btab_btn_timeline button:hover {{
    background-color: #252525 !important; color: #c9a84c !important;
}}
.st-key-btab_btn_history button:focus,
.st-key-btab_btn_history button:active,
.st-key-btab_btn_history button:focus-visible,
.st-key-btab_btn_quote button:focus,
.st-key-btab_btn_quote button:active,
.st-key-btab_btn_quote button:focus-visible,
.st-key-btab_btn_compare button:focus,
.st-key-btab_btn_compare button:active,
.st-key-btab_btn_compare button:focus-visible,
.st-key-btab_btn_timeline button:focus,
.st-key-btab_btn_timeline button:active,
.st-key-btab_btn_timeline button:focus-visible {{
    border-radius: 8px 8px 0 0 !important;
    outline: none !important; box-shadow: none !important;
}}
.st-key-btab_btn_history button p,
.st-key-btab_btn_quote button p,
.st-key-btab_btn_compare button p,
.st-key-btab_btn_timeline button p {{
    color: inherit !important; font-size: 13px !important; margin: 0 !important;
}}
.st-key-btab_btn_{_active_tid} button {{
    background-color: #c9a84c !important;
    color: #000000 !important; font-weight: 700 !important;
}}
.st-key-btab_btn_{_active_tid} button:hover {{
    background-color: #c9a84c !important; color: #000000 !important;
}}
.st-key-btab_btn_{_active_tid} button p {{
    color: #000000 !important;
}}
</style>
""", unsafe_allow_html=True)

    tab_cols = st.columns(len(_TABS))
    for col, (tid, tlabel) in zip(tab_cols, _TABS):
        with col:
            with st.container(key=f"btab_btn_{tid}"):
                if st.button(tlabel, key=f"btab_{tid}", use_container_width=True):
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
