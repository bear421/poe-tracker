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
from dataclasses import dataclass
from collections import defaultdict

EXPEDITION_RED_TEMPLATE = "assets/templates/expedition_red.png"
EXPEDITION_GREY_TEMPLATE = "assets/templates/expedition_grey.png"
COLOR_NORMAL = (75, 75, 75)
COLOR_MAGIC = (46, 57, 96)
COLOR_RARE = (96, 85, 32)

@dataclass
class EncounterCtx:
    image: np.ndarray
    image_gs: Optional[np.ndarray] = None
    image_hsv: Optional[np.ndarray] = None
    _image_current: Optional[np.ndarray] = None
    debug_info = defaultdict(list)
    current_debug_name: Optional[str] = None
    debug: bool = False

    def get_image_gs(self):
        if self.image_gs is None:
            self.image_gs = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self._image_current = self.image_gs
        return self.image_gs

    def get_image_hsv(self):
        if self.image_hsv is None:
            self.image_hsv = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
        self._image_current = self.image_hsv
        return self.image_hsv

    def get_current_image(self):
        return self._image_current if self._image_current is not None else self.image

    def set_current_debug_name(self, name: str):
        self.current_debug_name = name

    def add_debug_info(self, info: Dict[str, Any]):
        if not self.current_debug_name:
            raise ValueError("current_debug_name is not set")

        self.debug_info[self.current_debug_name].append(info)

def is_breach(ctx: EncounterCtx) -> Optional[Dict]:
    """Detect if a breach encounter is present in the image."""
    debug_info = {
        "steps": []
    }

    debug_info["steps"].append("Image loaded successfully")

    # Convert to HSV for color filtering
    hsv = ctx.get_image_hsv()
    debug_info["steps"].append("Converted image to HSV")

    # Define color ranges for purple (main hand)
    purple_lower = np.array([130, 80, 80])  # Adjusted for better specificity
    purple_upper = np.array([160, 255, 255])

    # Create mask
    purple_mask = cv2.inRange(hsv, purple_lower, purple_upper)
    debug_info["steps"].append("Created purple mask")

    # Find contours for purple (main breach hand)
    purple_contours, _ = cv2.findContours(purple_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    debug_info["steps"].append(f"Found {len(purple_contours)} contours")

    # Define shape and size constraints
    detected = False
    for cnt in purple_contours:
        area = cv2.contourArea(cnt)

        if area > 400:  # Area threshold
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h
            debug_info["steps"].append(f"Bounding box: ({x}, {y}, {w}, {h}), Aspect ratio: {aspect_ratio}")

            # Ensure aspect ratio matches expected hand shape
            if 0.4 < aspect_ratio < 2:
                mask = np.zeros_like(purple_mask)
                cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
                matching_pixels = cv2.bitwise_and(purple_mask, purple_mask, mask=mask)
                match_percentage = (np.sum(matching_pixels > 0) / area) * 100
                debug_info["steps"].append(f"Match percentage: {match_percentage}")

                if match_percentage > 35:  # At least 35% of the area must be purple
                    detected = True
                    debug_info["steps"].append("Detection criteria met")
                    break

    return ("Breach", {}) if detected else (None, None)

def is_ritual(ctx: EncounterCtx) -> Optional[Dict]:
    ctx.get_image_gs()
    contains_exactly = partial(_contains_exactly, ctx = ctx, threshold=0.5, scale=0.5, font_size=25, font_color=(255, 255, 255))
    altar_types = ["Smothered", "Infested", "Tainted", "Contaminated", "Sapping"]
    if not contains_exactly("Ritual"):
        return (None, None)

    maybe_completed = contains_exactly("Ritual Rewards")
    maybe_not_completed = contains_exactly("Ritual Altar")
    # check for symmetry to avoid false positive in fast check
    if maybe_completed != maybe_not_completed:
        completed = maybe_completed
    elif not maybe_completed:
        return (None, None)
    else:
        completed = contains_exactly("Ritual Rewards", threshold=0.55, scale=0.5)
    suffix = "Rewards" if completed else "Altar"
    for altar_type in altar_types:
        text = f"{altar_type} Ritual {suffix}"
        if contains_exactly(text, threshold=0.65, scale=0.5):
            return ("Ritual", {"altar_type": altar_type, "completed": completed})
    return (None, None)

def is_strongbox(ctx: EncounterCtx) -> Optional[Dict]:
    ctx.get_image_gs()
    contains_exactly = partial(_contains_exactly, ctx = ctx, threshold=0.5, scale=0.5, font_size=30, font_color=COLOR_RARE)
    strongbox_types = ["Ornate", "Researcher's", "Armourer's", "Blacksmith's", ""] # "" = normal Strongbox
    if not contains_exactly("Strongbox"):
        return (None, None)
    for strongbox_type in strongbox_types:
        text = f"{strongbox_type} Strongbox"
        for color in [COLOR_NORMAL, COLOR_MAGIC, COLOR_RARE]:
            if contains_exactly(text, threshold=0.7, scale=0.5, font_color=color): 
                rarity = "Normal" if color == COLOR_NORMAL else "Magic" if color == COLOR_MAGIC else "Rare"
                return ("Strongbox", {"strongbox_type": strongbox_type, "rarity": rarity})
    return (None, None)

def is_essence(ctx: EncounterCtx) -> Optional[Dict]:
    ctx.get_image_gs()
    essence_types = ["the Body", "the Mind", "Enhancement", "Torment", "Flames", "Ice", "Electricity", "Ruin", "Battle", "Sorcery", "Haste", "the Infinite"]
    contains_exactly = partial(_contains_exactly, ctx=ctx, threshold=0.5, scale=0.5, font_size=25, font_color=COLOR_RARE)
    n_essences = 0
    # todo check all anchors for multiple essences
    if not contains_exactly("Essence of"):
        return (None, None)
    maybe_greater = contains_exactly("Greater Essence of")
    greater = maybe_greater and contains_exactly("Greater Essence of", threshold=0.7, scale=0.5)
    for essence_type in essence_types:
        text = f"Essence of {essence_type}"
        if contains_exactly(text, threshold=0.65, scale=0.5): 
            return ("Essence", {"essence_types": [text], "greater": greater})
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

def is_expedition(ctx: EncounterCtx) -> Optional[Dict]:
    """Detect if an Expedition encounter is present using feature-based matching with SIFT."""

    # Load the templates
    template_red = cv2.imread(EXPEDITION_RED_TEMPLATE, cv2.IMREAD_GRAYSCALE)
    template_grey = cv2.imread(EXPEDITION_GREY_TEMPLATE, cv2.IMREAD_GRAYSCALE)

    if template_red is None or template_grey is None:
        raise FileNotFoundError("Could not load one or both Expedition templates")

    # Convert the target image to grayscale
    image_gray = ctx.get_image_gs()

    # Initialize SIFT detector
    sift = cv2.SIFT_create()

    # Detect keypoints and descriptors in the image and templates
    kp_image, des_image = sift.detectAndCompute(image_gray, None)
    kp_red, des_red = sift.detectAndCompute(template_red, None)
    kp_grey, des_grey = sift.detectAndCompute(template_grey, None)

    # Initialize the BFMatcher
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)

    # Match descriptors for red template
    matches_red = bf.match(des_image, des_red)
    matches_red = sorted(matches_red, key=lambda x: x.distance)

    # Match descriptors for grey template
    matches_grey = bf.match(des_image, des_grey)
    matches_grey = sorted(matches_grey, key=lambda x: x.distance)

    # Define a match threshold
    match_threshold = 90  # Adjust based on experimentation

    # Check if sufficient matches are found for either template
    if len(matches_red) > match_threshold:
        return {"name": "Expedition", "is_armed": True}

    return (None, None)

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

def _contains_exactly(text, ctx: EncounterCtx, threshold=0.5, scale=1.0, font_size=25, font_color=COLOR_NORMAL):
    if scale > 1.0:
        raise ValueError("scale must be lte 1.0")
    
    image = ctx.get_current_image()
    font = simple_ocr.load_font(font_size * scale)
    template = simple_ocr.text_template(text, font=font, color=font_color)
    if scale < 1.0:
        tiny_image = simple_ocr.resize_image(image, scale)
        tiny_template = template
    else:
        tiny_image = image
        tiny_template = template
    if ctx.debug:
        anchors = simple_ocr.find_anchor_points(tiny_image, tiny_template, threshold=threshold)
        visualization = simple_ocr.visualize_anchors(tiny_image, tiny_template, anchors)
        ctx.add_debug_info({
            "image": tiny_image, 
            "template": tiny_template, 
            "visualization": visualization,
            "scale": scale, 
            "threshold": threshold, 
            "font_size": font_size, 
            "font_color": font_color,
            "anchors": anchors
        })
    return simple_ocr.contains_template(tiny_image, tiny_template, threshold=threshold)

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
        if not name:
            name = auto_name
            data = {}
        data["_took"] = end - start
        data["_debug_info"] = ctx.debug_info.get(auto_name, [])
        encounters.append((name, data))
    return encounters

# Example usage
if __name__ == "__main__":
    for i in range(1, 9):
        image_path = f"encounter{i}.png"
        try:
            encounter_type = get_encounter_type(image_path)
            print(f"Image: {image_path}, Encounter Type: {encounter_type}")
        except FileNotFoundError as e:
            print(e)
