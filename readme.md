# install python dependencies
pip install --only-binary :all: numpy opencv-python pillow keyboard mouse pynput pygetwindow pyautogui pyperclip psutil pyttsx3 pyee requests freetype-py scikit-image

# ocr dependencies
pip install --only-binary :all: pytesseract
# fast screenshots, but with overlays
pip install --only-binary :all: d3dshot