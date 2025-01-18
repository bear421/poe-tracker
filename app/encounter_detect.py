import cv2
import pytesseract
import numpy as np
from PIL import Image
import imagehash
from PIL.Image import Image as PILImage

EXPEDITION_RED_TEMPLATE = "assets/templates/expedition_red.png"
EXPEDITION_GREY_TEMPLATE = "assets/templates/expedition_grey.png"

def is_breach(image):
    """Detect if a breach encounter is present in the image."""
    debug_info = {
        "steps": []
    }

    debug_info["steps"].append("Image loaded successfully")

    # Convert to HSV for color filtering
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
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

    return detected

def is_ritual(image):
    """Detect the reddish box that outlines the ritual rewards panel."""

    # Convert to HSV for color filtering
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Define reddish color range
    reddish_lower = np.array([0, 50, 50])  # Adjust hue/saturation/value as needed
    reddish_upper = np.array([10, 255, 255])

    # Create mask for reddish color
    reddish_mask = cv2.inRange(hsv, reddish_lower, reddish_upper)

    # Find contours
    contours, _ = cv2.findContours(reddish_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Iterate over contours to detect box-like shapes
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:  # Adjust area threshold for different resolutions
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h

            # Check if the contour has a box-like aspect ratio
            if 0.8 < aspect_ratio < 1.2:
                return True

    return False

def is_boss(image):
    """Detect if a boss encounter is present by looking for the big red health bar at the top."""

    # Convert to HSV for color filtering
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

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

def is_expedition(image):
    """Detect if an Expedition encounter is present using feature-based matching with SIFT."""

    # Load the templates
    template_red = cv2.imread(EXPEDITION_RED_TEMPLATE, cv2.IMREAD_GRAYSCALE)
    template_grey = cv2.imread(EXPEDITION_GREY_TEMPLATE, cv2.IMREAD_GRAYSCALE)

    if template_red is None or template_grey is None:
        raise FileNotFoundError("Could not load one or both Expedition templates")

    # Convert the target image to grayscale
    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

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

def get_encounter_type(image):
    opencv_image = image_to_opencv(image)
    """Determine the type of encounter in the image: Breach, Ritual, Boss, Expedition, or None."""
    if is_breach(opencv_image):
        return "Breach"
    elif is_boss(opencv_image):
        return "Boss"
    elif is_expedition(opencv_image):
        return "Expedition"
    elif is_ritual(opencv_image):
        return "Ritual"
    else:
        return None

# Example usage
if __name__ == "__main__":
    for i in range(1, 9):
        image_path = f"encounter{i}.png"
        try:
            encounter_type = get_encounter_type(image_path)
            print(f"Image: {image_path}, Encounter Type: {encounter_type}")
        except FileNotFoundError as e:
            print(e)
