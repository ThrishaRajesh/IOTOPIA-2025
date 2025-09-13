import streamlit as st
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image

# ---------------------------
# Helper Functions
# ---------------------------
def resize_images(imgA, imgB, max_dim=800):
    hA, wA = imgA.shape[:2]
    hB, wB = imgB.shape[:2]
    scale = min(max_dim/wA, max_dim/hA, max_dim/wB, max_dim/hB, 1)
    imgA = cv2.resize(imgA, (int(wA*scale), int(hA*scale)))
    imgB = cv2.resize(imgB, (int(wB*scale), int(hB*scale)))
    h = min(imgA.shape[0], imgB.shape[0])
    w = min(imgA.shape[1], imgB.shape[1])
    imgA = imgA[:h, :w]
    imgB = imgB[:h, :w]
    return imgA, imgB

def compare_absdiff(grayA, grayB, threshold):
    diff = cv2.absdiff(grayA, grayB)
    _, th = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
    return th

def compare_ssim(grayA, grayB):
    score, diff = ssim(grayA, grayB, full=True)
    diff = (diff * 255).astype("uint8")
    inv = cv2.bitwise_not(diff)
    _, th = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return th

def postprocess(binary, min_area=1000):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    mask = np.zeros_like(binary)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            mask[labels == i] = 255
    return mask

def damage_score_color(pct):
    if pct < 5:
        return 0, (0,255,0)
    elif pct < 20:
        return 1, (0,255,255)
    elif pct < 50:
        return 2, (0,165,255)
    else:
        return 3, (0,0,255)

def overlay_damage_colored(after, mask, color, alpha=0.45):
    overlay = after.copy().astype("float32")
    color_layer = np.zeros_like(after, dtype=np.uint8)
    color_layer[:] = color
    mask_bool = mask.astype(bool)
    overlay[mask_bool] = (1-alpha)*after[mask_bool].astype("float32") + alpha*color_layer[mask_bool]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0,0,0), 2)
    return overlay.astype("uint8")

# ---------------------------
# Streamlit GUI
# ---------------------------
st.set_page_config(page_title="Damage Comparison", page_icon="", layout="wide")

st.markdown(
    """
    <style>
    body {
        background: linear-gradient(to right, #ffecd2, #fcb69f);
        color: #111;
        font-family: 'Arial', sans-serif;
    }
    h1 {
        text-align: center;
        font-size: 3.5rem;
        font-weight: bold;
        text-shadow: 2px 2px 6px #fff;
    }
    /* Center all main components */
    .block-container {
        max-width: 900px;
        margin: auto;
        text-align: center;
    }
    label, .stFileUploader label, .stSelectbox label, .stSlider label {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    .stButton>button {
        background: linear-gradient(to right, #ff7e5f, #feb47b);
        color: white;
        font-weight: bold;
        font-size: 22px;
        border-radius: 12px;
        height:55px;
        width:260px;
        transition: transform 0.2s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        cursor: pointer;
    }
    .stAlert, .stSuccess, .stError {
        font-size: 18px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Before/After Damage Comparison")

# Uploaders and controls
before_file = st.file_uploader("Upload BEFORE image", type=["jpg","png","jpeg"])
after_file = st.file_uploader("Upload AFTER image", type=["jpg","png","jpeg"])
method = st.selectbox("Choose Comparison Method", ["AbsDiff", "SSIM"])
threshold = st.slider("Set Threshold", 0, 100, 30) if method=="AbsDiff" else None

analyze = st.button("Analyze Damage")

# Results
if analyze:
    if before_file and after_file:
        imgA = np.array(Image.open(before_file))
        imgB = np.array(Image.open(after_file))
        imgA = cv2.cvtColor(imgA, cv2.COLOR_RGB2BGR)
        imgB = cv2.cvtColor(imgB, cv2.COLOR_RGB2BGR)
        imgA, imgB = resize_images(imgA, imgB)
        grayA = cv2.GaussianBlur(cv2.cvtColor(imgA, cv2.COLOR_BGR2GRAY), (5,5), 0)
        grayB = cv2.GaussianBlur(cv2.cvtColor(imgB, cv2.COLOR_BGR2GRAY), (5,5), 0)

        raw_mask = compare_absdiff(grayA, grayB, threshold) if method=="AbsDiff" else compare_ssim(grayA, grayB)
        mask = postprocess(raw_mask, min_area=1000)

        total = mask.size
        damaged = cv2.countNonZero(mask)
        pct = (damaged / total) * 100
        score, color = damage_score_color(pct)
        overlay = overlay_damage_colored(imgB, mask, color)

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.image(imgA[:,:,::-1], caption="Before", use_container_width=True)
        with col2:
            st.image(overlay[:,:,::-1], caption=f"After Damage (Score {score})", use_container_width=True)

        st.success(f"Detected damage: {pct:.2f}% → {['No damage','Minor','Major','Destroyed'][score]}")
        st.markdown("<h3>Damage Level Explanation</h3>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="font-size:18px; text-align:center;">
            - <span style="color:green;">Green (0)</span> → No damage <br>
            - <span style="color:gold;">Yellow (1)</span> → Minor damage <br>
            - <span style="color:orange;">Orange (2)</span> → Major damage <br>
            - <span style="color:red;">Red (3)</span> → Destroyed <br>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error("Please upload both BEFORE and AFTER images!")
