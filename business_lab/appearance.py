"""Session-local presentation. No global Streamlit config changes between users."""


def palette(mode):
    if mode == "dark":
        return dict(
            background="#101b24", surface="#172832", text="#e7eff3", muted="#b2c4cd", border="#36505d", accent="#45c7b3"
        )
    return dict(
        background="#ffffff", surface="#f0f4f4", text="#172d35", muted="#536b75", border="#ccd9dd", accent="#137d73"
    )


def css(mode):
    p = palette(mode)
    return f"""<style>
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stHeader"] {{background:{p["background"]};color:{p["text"]};}}
[data-testid="stSidebar"], [role="dialog"], [role="listbox"], [role="option"] {{background:{p["surface"]};color:{p["text"]};}}
[data-testid="stApp"] h1,[data-testid="stApp"] h2,[data-testid="stApp"] h3,
[data-testid="stApp"] [role="tab"], [data-testid="stApp"] label,[data-testid="stApp"] p,[data-testid="stApp"] summary,
[data-testid="stMetricLabel"],[data-testid="stMetricValue"], [data-testid="stWidgetLabel"] {{color:{p["text"]};}}
[data-testid="stCaptionContainer"] {{opacity:1;}}
[data-testid="stCaptionContainer"] p {{color:{p["muted"]};}}
[data-testid="stBaseButton-primary"] {{background:{p["accent"]};border-color:{p["accent"]};color:{p["background"]};}}
[data-testid="stBaseButton-primary"] p {{color:{p["background"]};}}
[data-testid="stApp"] button:focus-visible,[data-testid="stApp"] a:focus-visible {{outline:2px solid {p["accent"]};outline-offset:3px;}}
[data-testid="stMetric"], [data-testid="stForm"], [data-testid="stExpander"] {{border-color:{p["border"]};}}
[data-testid="stApp"] input, [data-testid="stApp"] textarea,
[data-testid="stApp"] [role="combobox"], [data-baseweb="select"]>div,
[data-testid="stSelectbox"] button, [data-testid="stMultiSelect"] button,
[data-testid="stNumberInputContainer"], [data-testid="stNumberInputContainer"] button,
[data-testid="stFileUploaderDropzone"], [data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-headerNoPadding"], [data-testid="stBaseButton-header"] {{background:{p["surface"]};color:{p["text"]};border-color:{p["border"]};}}
[data-testid="stApp"] a {{color:{p["accent"]};}}
[data-testid="stAlert"] {{background:{p["surface"]};border:1px solid {p["border"]};border-radius:8px;}}
[data-testid="stAlert"] p {{color:{p["text"]};}}
[data-testid="stDataFrame"] {{--gdg-bg-cell:{p["surface"]};--gdg-bg-header:{p["background"]};--gdg-text-dark:{p["text"]};}}
</style>"""
