import cv2
import pytesseract
import numpy as np
from PIL import Image
import imagehash
import simple_ocr
from PIL.Image import Image as PILImage
from typing import Optional, Dict, Any
from functools import partial
import time
from PySide6.QtGui import QFont
from dataclasses import dataclass
from collections import defaultdict
from Levenshtein import distance as Levenshtein


EXPEDITION_RED_TEMPLATE = "assets/templates/expedition_red.png"
EXPEDITION_GREY_TEMPLATE = "assets/templates/expedition_grey.png"
COLOR_WHITE = (255, 255, 255)
COLOR_NORMAL = (75, 75, 75)
COLOR_MAGIC = (46, 57, 96)
COLOR_RARE = (96, 85, 32)

@dataclass
class EncounterCtx:
    image: np.ndarray
    image_gs: Optional[np.ndarray] = None
    image_gs_small: Optional[np.ndarray] = None
    image_hsv: Optional[np.ndarray] = None
    debug_info = defaultdict(list)
    current_debug_name: Optional[str] = None
    debug: bool = False

    def get_image_gs(self):
        if self.image_gs is None:
            self.image_gs = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        return self.image_gs

    def get_image_gs_small(self):
        if self.image_gs_small is None:
            self.image_gs_small = simple_ocr.resize_image(self.get_image_gs(), 0.5)
        return self.image_gs_small

    def get_image_hsv(self):
        if self.image_hsv is None:
            self.image_hsv = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
        return self.image_hsv

    def set_current_debug_name(self, name: str):
        self.current_debug_name = name

    def add_debug_info(self, info: Dict[str, Any]):
        if not self.current_debug_name:
            raise ValueError("current_debug_name is not set")

        self.debug_info[self.current_debug_name].append(info)

def is_breach(ctx: EncounterCtx) -> Optional[Dict]:
    """Detect if a breach encounter is present in the image."""
    # Convert to HSV for color filtering
    hsv = ctx.get_image_hsv()

    # Define color ranges for purple (main hand)
    purple_lower = np.array([130, 80, 80])  # Adjusted for better specificity
    purple_upper = np.array([160, 255, 255])

    purple_mask = cv2.inRange(hsv, purple_lower, purple_upper)

    purple_contours, _ = cv2.findContours(purple_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detected = False
    for cnt in purple_contours:
        area = cv2.contourArea(cnt)
        if area > 400:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h

            if 0.4 < aspect_ratio < 2:
                mask = np.zeros_like(purple_mask)
                cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
                matching_pixels = cv2.bitwise_and(purple_mask, purple_mask, mask=mask)
                match_percentage = (np.sum(matching_pixels > 0) / area) * 100

                if match_percentage > 35:  # At least 35% of the area must be purple
                    detected = True
                    break

    return ("Breach", {}) if detected else (None, None)

_RITUAL_ALTAR_TYPES = ["Smothered", "Infested", "Tainted", "Contaminated", "Sapping"]

def is_ritual(ctx: EncounterCtx) -> Optional[Dict]:
    scale = 0.5
    image = ctx.get_image_gs_small()
    find_anchors = partial(_find_anchors, ctx = ctx, image=image, threshold=0.5, font_size=18 * scale, font_color=(255, 255, 255))
    anchors, template = find_anchors("Ritual")
    if not anchors:
        return (None, None)
    
    head_anchor = anchors[0]
    x1, y1, x2, y2 = expand_anchor(head_anchor, template, m=1.5, left_m=2, right_m=2)
    cropped_image = image[y1:y2, x1:x2]
    if ctx.debug:
        ctx.add_debug_info({
            "cropped_image": cropped_image
        })
    ocr_text = pytesseract.image_to_string(cropped_image, config="--psm 6 --oem 3")
    lines = ocr_text.strip().split('\n')
    completed = False
    for line in lines:
        if Levenshtein(line.strip().lower(), "ritual rewards") <= 3:
            completed = True
        elif Levenshtein(line.strip().lower(), "ritual altar") <= 3:
            completed = False
        for altar_type in _RITUAL_ALTAR_TYPES:
            name = f"{altar_type} Ritual Altar" 
            if Levenshtein(line.strip().lower(), name.lower().strip()) <= 4:
                if completed:  # discard completed ritual encounters for now, misleading
                    return (None, None)
                return ("Ritual", {"altar_type": altar_type, "completed": completed})

    return (None, None)

_STRONGBOX_TYPES = ["Arcane","Ornate", "Researcher's", "Armourer's", "Blacksmith's", "Jeweller's", "Large", "Cartographer's", ""] # "" = normal Strongbox

def is_strongbox(ctx: EncounterCtx) -> Optional[Dict]:
    scale = 0.5
    image = ctx.get_image_gs_small()
    find_anchors = partial(_find_anchors, ctx = ctx, image = image, threshold=0.5, font_size=24 * scale, font_color=(193, 193, 193))
    anchors, template = find_anchors("Strongbox")
    if not anchors:
        return (None, None)
    head_anchor = anchors[0]
    x1, y1, x2, y2 = expand_anchor(head_anchor, template, m=1.2, left_m=2)
    cropped_image = image[y1:y2, x1:x2]
    if ctx.debug:
        ctx.add_debug_info({
            "cropped_image": cropped_image
        })
    ocr_text = pytesseract.image_to_string(cropped_image, config="--psm 6 --oem 3")
    lines = ocr_text.strip().split('\n')
    for line in lines:
        for strongbox_type in _STRONGBOX_TYPES:
            name = f"{strongbox_type} Strongbox"
            if Levenshtein(line.strip().lower(), name.lower().strip()) <= 4:
                return ("Strongbox", {"name": name})
    return (None, None)

_ESSENCE_TYPES = ["the Body", "the Mind", "Enhancement", "Torment", "Flames", "Electricity", "Ruin", "Battle", "Sorcery", "Haste", "the Infinite", "Ice"]

def is_essence(ctx: EncounterCtx) -> Optional[Dict]:
    scale = 0.5
    image = ctx.get_image_gs_small()
    find_anchors = partial(_find_anchors, ctx=ctx, image=image, threshold=0.5, font_size=18 * scale, font_color=COLOR_RARE)
    anchors, template = find_anchors("Essence of")
    if not anchors:
        return (None, None)
    essences = []
    for anchor in anchors:
        x1, y1, x2, y2 = expand_anchor(anchor, template, m=1.2, left_m=1.5, right_m=2)
        cropped_image = image[y1:y2, x1:x2]
        if ctx.debug:
            ctx.add_debug_info({
                "cropped_image": cropped_image
            })
        ocr_text = pytesseract.image_to_string(cropped_image, config="--psm 6 --oem 3")
        lines = ocr_text.strip().split('\n')
        for line in lines:
            for size in ["", "Greater "]:
                for essence_type in _ESSENCE_TYPES:
                    name = f"{size}Essence of {essence_type}"
                    if Levenshtein(line.strip().lower(), name.lower().strip()) <= 4:
                        essences.append(name)   


    if essences:
        return ("Essence", {"essences": essences})
    return (None, None)


def is_expedition(ctx: EncounterCtx) -> Optional[Dict]:
    if _contains_text("Detonator", ctx):
        return ("Expedition", {"is_armed": False})
    if _contains_text("Detonate Explosives", ctx, font_color=(255, 0, 0)):
        return ("Expedition", {"is_armed": True})
    return (None, None)

def is_boss(ctx: EncounterCtx):
    """Detect if a boss encounter is present by looking for the big red health bar at the top."""

    # Convert to HSV for color filtering
    hsv = ctx.get_image_hsv()

    # Define red color range for the health bar
    red_lower1 = np.array([0, 50, 50])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([170, 50, 50])
    red_upper2 = np.array([180, 255, 255])

    # Create masks for both red ranges
    mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
    mask2 = cv2.inRange(hsv, red_lower2, red_upper2)

    # Combine masks
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Focus on the top part of the image where the health bar typically appears
    height, width = red_mask.shape
    top_region = red_mask[:int(height * 0.2), :]  # Top 20% of the image

    # Find contours in the top region
    contours, _ = cv2.findContours(top_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h

        # Check if the contour is wide and thin (typical of a health bar)
        if area > 1000 and aspect_ratio > 5:
            return True

    return False
    
def image_to_opencv(image):
    """
    Process an image input, which can be either a file path (string) or a PIL Image object.

    Args:
        image (str or PIL.Image.Image): The image to process.

    Returns:
        numpy.ndarray: The image in OpenCV format.

    Raises:
        TypeError: If the input is not a string or a PIL.Image.Image instance.
    """
    if isinstance(image, str):
        opencv_image = cv2.imread(image)
        if opencv_image is None:
            raise FileNotFoundError(f"Could not load image from path: {image}")
        return opencv_image
    elif isinstance(image, PILImage):
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    else:
        raise TypeError(f"Expected a file path (str) or a PIL.Image.Image, got {type(image).__name__}")

def _find_anchors(text, ctx: EncounterCtx, image=None, threshold=0.5, scale=1.0, font_size=25, font_color=COLOR_NORMAL):
    if scale > 1.0:
        raise ValueError("scale must be lte 1.0")
    font = simple_ocr.load_font_q(font_size * scale)
    font.setWeight(QFont.Weight(100))
    template = simple_ocr.text_template_q(text, font=font, color=font_color)
    if scale < 1.0:
        tiny_image = simple_ocr.resize_image(image, scale)
        tiny_template = template
    else:
        tiny_image = image
        tiny_template = template
    anchors = simple_ocr.find_unique_anchor_points(tiny_image, tiny_template, threshold=threshold)
    if ctx.debug:
        visualization = simple_ocr.visualize_anchors(tiny_image, tiny_template, anchors)
        ctx.add_debug_info({
            "text": text,
            "scale": scale, 
            "threshold": threshold, 
            "font_size": font_size, 
            "font_color": font_color,
            "anchors": anchors,
            "image": tiny_image, 
            "template": tiny_template, 
            "visualization": visualization
        })
    return (anchors, template)

def _contains_text(text, ctx: EncounterCtx, image=None, threshold=0.5, scale=0.5, font_size=25, font_color=COLOR_NORMAL, levenshtein_threshold=4):
    if image is None:
        image = ctx.get_image_gs()
    if scale < 1.0:
        image = simple_ocr.resize_image(image, scale)
        font_size *= scale
    anchors, template = _find_anchors(text=text, ctx=ctx, image=image, threshold=threshold, font_size=font_size, font_color=font_color)
    if not anchors:
        return False

    head_anchor = anchors[0]
    x1, y1, x2, y2 = expand_anchor(head_anchor, template, m=1.2)
    cropped_image = image[y1:y2, x1:x2]
    if ctx.debug:
        ctx.add_debug_info({
            "cropped_image": cropped_image
        })
    ocr_text = pytesseract.image_to_string(cropped_image, config="--psm 6 --oem 3")
    lines = ocr_text.strip().split('\n')
    for line in lines:
        for size in ["", "Greater "]:
            for essence_type in _ESSENCE_TYPES:
                text = f"{size}Essence of {essence_type}"
                if Levenshtein(line.strip().lower(), text) <= levenshtein_threshold:
                    return True
    return False

def get_encounter_type(image):
    opencv_image = image_to_opencv(image)
    ctx = EncounterCtx(image=opencv_image)
    for algo in [is_breach, is_ritual, is_strongbox, is_expedition, is_essence]:
        start = time.time()
        (name, data) = algo(ctx)
        end = time.time()
        if name:
            print(f"Encounter detected: {name} in {end - start} seconds data: {data}")
            return (name, data)
    return (None, None)

def debug_encounters(image):
    opencv_image = image_to_opencv(image)
    ctx = EncounterCtx(image=opencv_image, debug=True)
    encounters = []
    for algo in [is_ritual, is_strongbox, is_essence, is_expedition, is_breach]:
        auto_name = algo.__name__.replace("is_", "").title()
        ctx.set_current_debug_name(auto_name)
        start = time.time()
        (name, data) = algo(ctx)
        end = time.time()
        info = {
            "data": data,
            "_took": end - start,
        }
        if name:
            info["match"] = True
        else:
            name = auto_name
            info["match"] = False
        info["_debug_info"] = ctx.debug_info.get(auto_name, [])
        encounters.append((name, info))
    return encounters

def expand_anchor(anchor: tuple[int, int], template: np.ndarray, m=0, left_m=0, right_m=0, top_m=0, bottom_m=0, bounds=None) -> tuple[int, int, int, int]:
    """
    Expands a box around an anchor point by multipliers of template dimensions.
    The expansion scales proportionally from the initial template bounds.
    """
    x, y = anchor
    h, w = template.shape[:2]

    x1 = int(x - w * left_m - w * m * 0.5)    
    y1 = int(y - h * top_m - h * m * 0.5)
    x2 = int((x + w) + w * right_m + w * m * 0.5)
    y2 = int((y + h) + h * bottom_m + h * m * 0.5)

    if bounds:
        width, height = bounds
        x1 = max(0, x1)
        x2 = min(width, x2)
        y1 = max(0, y1)
        y2 = min(height, y2)

    return (x1, y1, x2, y2)


# Example usage
if __name__ == "__main__":
    for i in range(1, 9):
        image_path = f"encounter{i}.png"
        try:
            encounter_type = get_encounter_type(image_path)
            print(f"Image: {image_path}, Encounter Type: {encounter_type}")
        except FileNotFoundError as e:
            print(e)
