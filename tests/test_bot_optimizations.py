import sys
import types

from PIL import Image

sys.modules.setdefault("pyautogui", types.SimpleNamespace(
    screenshot=lambda *args, **kwargs: None,
    PAUSE=0.0,
    FAILSAFE=False,
    click=lambda *args, **kwargs: None,
    hotkey=lambda *args, **kwargs: None,
    press=lambda *args, **kwargs: None,
    pixel=lambda *args, **kwargs: (0, 0, 0),
    position=lambda: types.SimpleNamespace(x=0, y=0),
))
sys.modules.setdefault("keyboard", types.SimpleNamespace(add_hotkey=lambda *args, **kwargs: None, wait=lambda: None))
sys.modules.setdefault("pyperclip", types.SimpleNamespace(copy=lambda *args, **kwargs: None, paste=lambda *args, **kwargs: ""))

from bot import _detect_captcha_presence, duplicate_key


def test_detect_captcha_presence_rejects_blank_image():
    blank = Image.new("RGB", (100, 100), color=(255, 255, 255))
    assert _detect_captcha_presence(blank) is False


def test_detect_captcha_presence_accepts_text_like_image():
    image = Image.new("RGB", (100, 100), color=(255, 255, 255))
    for x in range(10, 90):
        image.putpixel((x, 50), (0, 0, 0))
    assert _detect_captcha_presence(image) is True


def test_duplicate_key_normalizes_whitespace_and_case():
    assert duplicate_key("  Ab  C  ") == "abc"
