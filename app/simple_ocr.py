import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image, ImageDraw, ImageFont
import freetype
from typing import Optional
import imagehash
import timeit
from functools import lru_cache
import time
FONT_PATH = "assets/fonts/Fontin-SmallCaps.otf"

@lru_cache(maxsize=32)
def load_font(font_size=25.5, font_path = FONT_PATH):
    return ImageFont.truetype(font_path, font_size)

def load_font_templates(font_path, chars, font_size=32, preprocess=True):
    """Load rendered font characters as templates."""
    face = freetype.Face(font_path)
    face.set_pixel_sizes(0, font_size)
    templates = {}
    for char in chars:
        face.load_char(char)
        bitmap = face.glyph.bitmap
        img = np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, bitmap.width)
        templates[char] = _preprocess_image(img) if preprocess else img
    return templates

@lru_cache(maxsize=128)
def text_template(text, font, color=(255, 255, 255)):
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    # text_height = bbox[3] - bbox[1]
    ascent, descent = font.getmetrics()
    text_height = ascent + descent
    if isinstance(color, tuple) and len(color) == 3:
        # rgb to grayscale
        color = int(0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2])
    image = Image.new("L", (text_width, text_height), 0)

    draw = ImageDraw.Draw(image)
    draw.text((0, 0), text, font=font, fill=color)
    template = np.array(image)
    return template

def _preprocess_image(img):
    """Crop and binarize the text region from the screenshot."""
    img = cv2.GaussianBlur(img, (3, 3), 0)
    binarized = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return binarized

def contains_exactly(text, image, font, threshold=0.7):
    """Check if the text is present in the image."""
    template = text_template(text, font)
    anchor_points = find_anchor_points(image, template, threshold=threshold)
    if len(anchor_points) > 0:
        return True
    return False

def _num_channels(image):
    if len(image.shape) > 2:
        return image.shape[-1]
    return 1

def resize_image(image, scale):
    height, width = image.shape[:2]
    return cv2.resize(image, (int(width * scale), int(height * scale)))

def find_anchor_points(image, template, threshold=0.5):
    """Find all anchor points of a specific template in the image."""
    if _num_channels(image) != _num_channels(template):
        raise ValueError(f"Image and template must have the same number of channels, {_num_channels(image)} != {_num_channels(template)}")
    res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

    # Find all positions where the match score exceeds the threshold
    anchor_points = np.where(res >= threshold)
    anchor_points = list(zip(anchor_points[1], anchor_points[0]))  # Convert to (x, y) format
    return anchor_points

def contains_template(image, template, threshold=0.5):
    anchor_points = find_anchor_points(image, template, threshold=threshold)
    return len(anchor_points) > 0

def visualize_anchors(image, template, anchor_points):
    """Visualize all anchor points on the image."""
    vis_image = image
    # vis_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)  # Convert to BGR for visualization
    h, w = template.shape[:2]
    for x, y in anchor_points:
        # Draw rectangles around all matched areas
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), (66, 255, 77), 2)
    cv2.imshow("All Anchor Points Visualization", vis_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def safe_ssim(region, template, default_win_size=7):
    """Safely compute SSIM with dynamic win_size adjustment and matching dimensions."""
    # Ensure region and template have the same dimensions
    if region.shape != template.shape:
        template = cv2.resize(template, (region.shape[1], region.shape[0]))

    # Check dimensions after resizing
    if region.shape[0] < default_win_size or region.shape[1] < default_win_size:
        raise ValueError(
            f"Region size {region.shape} is too small for the default win_size ({default_win_size}). "
            "Ensure regions are properly cropped or use smaller text regions."
        )

    # Dynamically adjust win_size to the smaller side of the images
    win_size = min(region.shape[0], region.shape[1], default_win_size)

    # Ensure win_size is odd
    if win_size % 2 == 0:
        win_size -= 1

    # Compute SSIM
    return ssim(region, template, win_size=win_size)

def highlight_region(image, region_coords, window_name="Highlighted Region"):
    """
    Highlight the current region on the entire image.
    :param image: The entire image (grayscale or color).
    :param region_coords: Tuple (x, y, width, height) representing the region.
    :param window_name: Name of the display window.
    """
    print("region_coords:", region_coords)
    x, y, width, height = region_coords

    # Make a copy of the image to avoid modifying the original
    highlighted_image = image.copy()

    # If the image is grayscale, convert it to color for visualization
    if len(image.shape) == 2:
        highlighted_image = cv2.cvtColor(highlighted_image, cv2.COLOR_GRAY2BGR)

    # Draw a rectangle around the region
    cv2.rectangle(highlighted_image, (x, y), (x + width, y + height), (0, 255, 0), 2)  # Green box

    # Show the image with the highlighted region
    cv2.imshow(window_name, highlighted_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def show_image(image, window_name="Image"):
    cv2.imshow(window_name, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def safe_ssim(region, template, default_win_size=7):
    if region.shape != template.shape:
        template = cv2.resize(template, (region.shape[1], region.shape[0]))

    win_size = min(region.shape[0], region.shape[1], template.shape[0], template.shape[1], default_win_size)
    if win_size % 2 == 0:
        win_size -= 1

    return ssim(region, template, win_size=win_size)

def ncc_match(region, template):
    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    return np.max(result)

def mse_match(region, template):
    return np.mean((region.astype("float") - template.astype("float")) ** 2)

def histogram_match(region, template):
    hist_region = cv2.calcHist([region], [0], None, [256], [0, 256])
    hist_template = cv2.calcHist([template], [0], None, [256], [0, 256])
    return cv2.compareHist(hist_region, hist_template, cv2.HISTCMP_CORREL)

def hash_match(region, template):
    resized_template = cv2.resize(template, (region.shape[1], region.shape[0]))
    hash_region = imagehash.average_hash(Image.fromarray(region))
    hash_template = imagehash.average_hash(Image.fromarray(resized_template))
    return -abs(hash_region - hash_template)

def test6(text):
    import time
    font = ImageFont.truetype(FONT_PATH, 25.5)
    template = text_template(text, font)
    cv2.imshow("template", template)
    # template = _preprocess_image(template)
    template = resize_image(template, 0.1)
    image = "encounters/smothered_ritual_altar.png"
    image = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
    image = resize_image(image, 0.1)
    #image = _preprocess_image(image)
    image = image.astype(np.uint8)
    start_time = time.time()
    anchor_points = find_anchor_points(image, template, threshold=0.6)
    end_time = time.time()
    visualize_anchors(image, template, anchor_points)
    print("contains_exactly:", anchor_points)
    print(f"Elapsed time: {end_time - start_time:.6f} seconds")

if __name__ == "__main__":
    test6("Smothered Ritual Altar")
    test6("Ritual Altar")
    #elapsed = timeit.timeit("test5()", globals=globals(), number=10)
    #print(f"Elapsed time: {elapsed:.6f} seconds for 10 runs")
    #print(test4())

