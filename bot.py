from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import keyboard
import pyautogui
import pyperclip
import requests


DEFAULT_CAPTURE_REGION = (700, 193, 478, 205)  # x, y, width, height
DEFAULT_INPUT_BOX = (100, 325)
DEFAULT_SUBMIT_BUTTON = (200, 400)
DEFAULT_PLAY_BUTTON = (0, 0)
DEFAULT_STATUS_POINT = (0, 0)

DEFAULT_NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-nano-vl-8b-v1"

OCR_MODE_ALIASES = {
    "ai": "nvidia",
    "easy": "easyocr",
    "fast": "easyocr",
    "local": "easyocr",
    "nim": "nvidia",
}


@dataclass(frozen=True)
class Config:
    capture_region: tuple[int, int, int, int]
    loop_delay_seconds: float
    change_cooldown_seconds: float
    post_change_settle_seconds: float
    process_initial_frame: bool
    ocr_mode: str
    easyocr_languages: tuple[str, ...]
    easyocr_gpu: bool
    easyocr_min_confidence: float
    nvidia_api_url: str
    nvidia_model: str
    nvidia_api_key: str
    ai_timeout_seconds: float
    ai_connect_timeout_seconds: float
    ai_max_tokens: int
    ai_fallback_min_interval_seconds: float
    duplicate_text_window_seconds: float
    min_seconds_between_submissions: float
    paste_delay_seconds: float
    submit_delay_seconds: float
    play_delay_seconds: float
    clear_input_before_paste: bool
    pyautogui_pause: float
    pyautogui_failsafe: bool
    min_captcha_length: int
    max_captcha_length: int
    character_replacements: dict[str, str]
    status_point: tuple[int, int]


def load_dotenv() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_float(name: str, default: float) -> float:
    value = env_str(name)
    if not value:
        return default

    try:
        return float(value)
    except ValueError:
        print(f"Invalid {name}={value!r}; using {default}")
        return default


def env_int(name: str, default: int) -> int:
    value = env_str(name)
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        print(f"Invalid {name}={value!r}; using {default}")
        return default


def parse_int_tuple(
    name: str,
    expected_length: int,
    fallback: tuple[int, ...],
) -> tuple[int, ...]:
    value = env_str(name)
    if not value:
        return fallback

    try:
        parsed = tuple(int(part.strip()) for part in value.split(","))
    except ValueError:
        print(f"Invalid {name}={value!r}; using {format_tuple(fallback)}")
        return fallback

    if len(parsed) != expected_length:
        print(f"Invalid {name}={value!r}; using {format_tuple(fallback)}")
        return fallback

    return parsed


def parse_languages(value: str) -> tuple[str, ...]:
    languages = tuple(part.strip() for part in value.split(",") if part.strip())
    return languages or ("en",)


def parse_ocr_mode(value: str) -> str:
    mode = OCR_MODE_ALIASES.get(value.strip().lower(), value.strip().lower())
    if mode in {"accurate", "easyocr", "hybrid", "nvidia"}:
        return mode

    print(f"Invalid OCR_MODE={value!r}; using hybrid")
    return "hybrid"


def read_config() -> Config:
    import json
    replacements_str = env_str("CHARACTER_REPLACEMENTS_JSON", "")
    replacements = {}
    if replacements_str:
        try:
            replacements = json.loads(replacements_str)
        except Exception as e:
            print(f"Error parsing CHARACTER_REPLACEMENTS_JSON: {e}")

    return Config(
        capture_region=parse_int_tuple("CAPTURE_REGION", 4, DEFAULT_CAPTURE_REGION),
        loop_delay_seconds=env_float("LOOP_DELAY_SECONDS", 0.15),
        change_cooldown_seconds=env_float("CHANGE_COOLDOWN_SECONDS", 10.0),
        post_change_settle_seconds=env_float("POST_CHANGE_SETTLE_SECONDS", 0.15),
        process_initial_frame=env_bool("PROCESS_INITIAL_FRAME", True),
        ocr_mode=parse_ocr_mode(env_str("OCR_MODE", env_str("OCR_ENGINE", "hybrid"))),
        easyocr_languages=parse_languages(env_str("EASYOCR_LANGUAGES", "en")),
        easyocr_gpu=env_bool("EASYOCR_GPU", False),
        easyocr_min_confidence=env_float("EASYOCR_MIN_CONFIDENCE", 0.7),
        nvidia_api_url=env_str("NVIDIA_API_URL", DEFAULT_NVIDIA_API_URL),
        nvidia_model=env_str("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL),
        nvidia_api_key=env_str("NVIDIA_API_KEY", env_str("NIM_API_KEY")),
        ai_timeout_seconds=env_float("AI_TIMEOUT_SECONDS", 8.0),
        ai_connect_timeout_seconds=env_float("AI_CONNECT_TIMEOUT_SECONDS", 2.0),
        ai_max_tokens=env_int("AI_MAX_TOKENS", 32),
        ai_fallback_min_interval_seconds=env_float(
            "AI_FALLBACK_MIN_INTERVAL_SECONDS",
            2.0,
        ),
        duplicate_text_window_seconds=env_float(
            "DUPLICATE_TEXT_WINDOW_SECONDS",
            10.0,
        ),
        min_seconds_between_submissions=env_float(
            "MIN_SECONDS_BETWEEN_SUBMISSIONS",
            0.7,
        ),
        paste_delay_seconds=env_float("PASTE_DELAY_SECONDS", 0.05),
        submit_delay_seconds=env_float("SUBMIT_DELAY_SECONDS", 0.05),
        play_delay_seconds=env_float("PLAY_DELAY_SECONDS", 1.0),
        clear_input_before_paste=env_bool("CLEAR_INPUT_BEFORE_PASTE", True),
        pyautogui_pause=env_float("PYAUTOGUI_PAUSE", 0.02),
        pyautogui_failsafe=env_bool("PYAUTOGUI_FAILSAFE", True),
        min_captcha_length=env_int("MIN_CAPTCHA_LENGTH", 6),
        max_captcha_length=env_int("MAX_CAPTCHA_LENGTH", 12),
        character_replacements=replacements,
        status_point=parse_int_tuple("STATUS_POINT", 2, DEFAULT_STATUS_POINT),
    )


def format_tuple(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def capture_screen(config: Config):
    return pyautogui.screenshot(region=config.capture_region)


def frame_hash(image: Any) -> str:
    rgb_image = image.convert("RGB")
    return hashlib.blake2b(rgb_image.tobytes(), digest_size=16).hexdigest()


def image_to_png_data_url(image: Any) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def clean_model_output(text: str) -> str:
    text = text.strip()
    # Remove markdown formatting characters (bold, italics, headers, etc.)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    
    # Strip common code blocks
    text = re.sub(r"^```(?:text)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    
    # Strip common prefixes like "Answer:", "Captcha:", "Text:", "Result:", "Value:", etc.
    # including "The answer is:", "The captcha is:"
    prefix_pattern = r"^(?:the\s+)?(?:captcha|answer|text|value|solution|challenge|result)(?:\s+is)?\s*[:=-]\s*"
    text = re.sub(prefix_pattern, "", text, flags=re.IGNORECASE).strip()
    
    # Strip quotes, backticks, and extra spaces again
    text = text.strip("\"'` ")

    lower_text = text.lower()
    if any(phrase in lower_text for phrase in ["sorry", "cannot read", "unable to", "don't see", "no text", "clear text", "i see", "loading spinner", "blinking cursor"]):
        return ""

    if lower_text in {"none", "no text", "no visible text", "n/a", ""}:
        return ""

    return text


def clean_detected_text(text: str, replacements: dict[str, str] = None) -> str:
    text = clean_model_output(text)
    if replacements:
        for old, new in replacements.items():
            text = text.replace(old, new)
    text = text.replace("\r", "").replace("\n", "")
    return "".join(text.split())



def duplicate_key(text: str) -> str:
    return " ".join(text.casefold().split())


class EasyOcrReader:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._reader = None
        self._load_failed = False

    def read_text(self, image: Any) -> str:
        reader = self._get_reader()
        if reader is None:
            return ""

        try:
            import numpy as np
            from PIL import Image, ImageEnhance

            # 1. Grayscale
            gray = image.convert("L")
            # 2. Resize 2.5x using LANCZOS or BICUBIC to improve resolution
            w, h = gray.size
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                try:
                    resample_filter = Image.ANTIALIAS
                except AttributeError:
                    resample_filter = Image.BICUBIC
            resized = gray.resize((int(w * 2.5), int(h * 2.5)), resample_filter)
            # 3. Double the contrast to make text bolder and background cleaner
            enhancer = ImageEnhance.Contrast(resized)
            enhanced = enhancer.enhance(2.0)

            results = reader.readtext(
                np.array(enhanced.convert("RGB")),
                detail=1,
                paragraph=False,
            )
        except Exception as exc:
            print(f"EasyOCR failed: {exc}")
            return ""

        parts: list[str] = []
        if not results:
            print("[EasyOCR] No text structures found at all in the image.")
        for result in results:
            if len(result) < 3:
                continue

            detected_text = str(result[1]).strip()
            confidence = float(result[2])
            if detected_text:
                if confidence >= self.config.easyocr_min_confidence:
                    parts.append(detected_text)
                    print(f"[EasyOCR] Detected text: {detected_text!r} (confidence: {confidence:.2f})")
                else:
                    print(f"[EasyOCR] Ignored low-confidence text: {detected_text!r} (confidence: {confidence:.2f} < threshold: {self.config.easyocr_min_confidence})")

        return " ".join(parts).strip()

    def _get_reader(self):
        if self._reader is not None:
            return self._reader

        if self._load_failed:
            return None

        try:
            import easyocr
        except ImportError as exc:
            self._load_failed = True
            print(f"EasyOCR unavailable: {exc}")
            return None

        try:
            self._reader = easyocr.Reader(
                list(self.config.easyocr_languages),
                gpu=self.config.easyocr_gpu,
            )
        except Exception as exc:
            self._load_failed = True
            print(f"EasyOCR could not initialize: {exc}")
            return None

        return self._reader


class NvidiaVisionClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._last_call_at = 0.0
        self._missing_key_reported = False

    def read_text(self, image: Any, stop_event: threading.Event | None = None) -> str:
        if not self.config.nvidia_api_key:
            if not self._missing_key_reported:
                print("NVIDIA fallback unavailable: NVIDIA_API_KEY is not set")
                self._missing_key_reported = True
            return ""

        now = time.monotonic()
        elapsed = now - self._last_call_at
        if elapsed < self.config.ai_fallback_min_interval_seconds:
            remaining = self.config.ai_fallback_min_interval_seconds - elapsed
            if stop_event is not None and stop_event.wait(remaining):
                return ""
            if stop_event is None:
                time.sleep(remaining)

        self._last_call_at = now
        payload = {
            "model": self.config.nvidia_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Transcribe the exact alphanumeric characters shown in the image. "
                                "Do NOT perform any calculations or solve any math problems. "
                                "For example, if the image shows '3+5', you must output '3+5' and NOT '8'. "
                                "Return ONLY the literal text from the image. "
                                "No explanations, no preamble, no markdown, no labels. "
                                "If the image does not contain any clear alphanumeric characters or CAPTCHA "
                                "(for example, if it is blank, contains only noise, a loading spinner, "
                                "a cursor, or UI element borders), you MUST output 'NONE'."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_png_data_url(image)},
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": self.config.ai_max_tokens,
            "stream": False,
        }

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    self.config.nvidia_api_url,
                    headers={
                        "Authorization": self._auth_header(),
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=(
                        self.config.ai_connect_timeout_seconds,
                        self.config.ai_timeout_seconds,
                    ),
                )
                response.raise_for_status()
                data = response.json()
                return clean_model_output(extract_message_content(data))
            except Exception as exc:
                print(f"[NVIDIA] Attempt {attempt} failed: {exc}")
                if attempt < 3:
                    if stop_event is not None and stop_event.wait(1.0):
                        return ""
                    elif stop_event is None:
                        time.sleep(1.0)
                else:
                    print("NVIDIA fallback failed after 3 attempts")
                    return ""

    def _auth_header(self) -> str:
        if self.config.nvidia_api_key.lower().startswith("bearer "):
            return self.config.nvidia_api_key

        return f"Bearer {self.config.nvidia_api_key}"


def extract_message_content(data: dict[str, Any]) -> str:
    message = data["choices"][0]["message"]
    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return " ".join(parts)

    return str(content)


class ScreenOcrBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.input_box = parse_int_tuple("INPUT_BOX", 2, DEFAULT_INPUT_BOX)
        self.submit_button = parse_int_tuple(
            "SUBMIT_BUTTON",
            2,
            DEFAULT_SUBMIT_BUTTON,
        )
        self.play_button = parse_int_tuple(
            "PLAY_BUTTON",
            2,
            DEFAULT_PLAY_BUTTON,
        )
        self.status_point = parse_int_tuple(
            "STATUS_POINT",
            2,
            DEFAULT_STATUS_POINT,
        )
        self.easyocr = EasyOcrReader(config)
        self.nvidia = NvidiaVisionClient(config)
        self._position_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_frame_hash: str | None = None
        self._last_change_at = 0.0
        self._last_submitted_at = 0.0
        self._recent_submissions: dict[str, float] = {}

    def start(self) -> None:
        with self._state_lock:
            if self._worker and self._worker.is_alive():
                print("Bot already running")
                return

            self._stop_event.clear()
            self._last_frame_hash = None
            self._last_change_at = 0.0
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()

        print(f"Bot started in {self.config.ocr_mode} mode")

    def stop(self) -> None:
        self._stop_event.set()
        print("Bot stopped")

    def calibrate_input_box(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.input_box = (position.x, position.y)
        print(f"Input box set to {position.x},{position.y}")

    def calibrate_submit_button(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.submit_button = (position.x, position.y)
        print(f"Submit button set to {position.x},{position.y}")

    def calibrate_play_button(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.play_button = (position.x, position.y)
        print(f"Play button set to {position.x},{position.y}")

    def calibrate_status_point(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.status_point = (position.x, position.y)
        print(f"Status point set to {position.x},{position.y}")

    def print_positions(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            input_box = self.input_box
            submit_button = self.submit_button
            play_button = self.play_button
            status_point = self.status_point

        print(f"Mouse position: {position.x},{position.y}")
        print(f"CAPTURE_REGION={format_tuple(self.config.capture_region)}")
        print(f"INPUT_BOX={format_tuple(input_box)}")
        print(f"SUBMIT_BUTTON={format_tuple(submit_button)}")
        print(f"PLAY_BUTTON={format_tuple(play_button)}")
        print(f"STATUS_POINT={format_tuple(status_point)}")

        try:
            image = capture_screen(self.config)
            debug_path = Path("debug_capture.png")
            image.save(debug_path)
            print(f"[Debug] Saved screenshot of CAPTCHA region to: {debug_path.resolve()}")
        except Exception as e:
            print(f"[Debug] Failed to save screenshot: {e}")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._step()
            except Exception as exc:
                print(f"Bot loop error: {exc}")

            self._stop_event.wait(self.config.loop_delay_seconds)

    def _step(self) -> None:
        image = capture_screen(self.config)
        detected_text = self._read_text(image)
        cleaned_text = clean_detected_text(detected_text, self.config.character_replacements)

        if not cleaned_text:
            return

        if len(cleaned_text) < self.config.min_captcha_length:
            print(f"[OCR] Ignored text too short: {cleaned_text!r} (length: {len(cleaned_text)} < min: {self.config.min_captcha_length})")
            return

        if len(cleaned_text) > self.config.max_captcha_length:
            print(f"[OCR] Ignored text too long: {cleaned_text!r} (length: {len(cleaned_text)} > max: {self.config.max_captcha_length})")
            return

        if self._is_recent_duplicate(cleaned_text):
            return

        self._wait_for_submit_cooldown()
        if self._stop_event.is_set():
            return

        self._paste_and_submit(cleaned_text)
        self._mark_submitted(cleaned_text)
        print(f"Submitted CAPTCHA: {cleaned_text}")

        check_start = time.monotonic()
        self._check_submission_status()
        check_duration = time.monotonic() - check_start

        # Wait a few seconds until new CAPTCHA comes and repeat
        remaining_cooldown = max(0.1, self.config.change_cooldown_seconds - check_duration)
        print(f"Waiting {remaining_cooldown:.1f} seconds for new CAPTCHA...")
        self._stop_event.wait(remaining_cooldown)

    def _check_submission_status(self) -> None:
        with self._position_lock:
            status_point = self.status_point

        if not status_point or status_point == (0, 0):
            return

        # Poll for up to 3.5 seconds
        start_time = time.monotonic()
        detected_status = None
        while time.monotonic() - start_time < 3.5:
            if self._stop_event.is_set():
                break
            try:
                # Get the pixel color at status_point
                r, g, b = pyautogui.pixel(*status_point)
                # Red-ish: r > 120 and r > g + 40 and r > b + 40
                if r > 120 and r > g + 40 and r > b + 40:
                    detected_status = "Wrong"
                    break
                # Green-ish: g > 120 and g > r + 40 and g > b + 20
                elif g > 120 and g > r + 40 and g > b + 20:
                    detected_status = "Correct"
                    break
            except Exception:
                # Sometimes pyautogui.pixel fails if coordinates are out of bounds
                pass
            time.sleep(0.1)

        if detected_status:
            print(f"Submission Result: {detected_status}")
        else:
            print("Submission Result: Unknown (No status banner detected)")

    def _read_text(self, image: Any) -> str:
        if self.config.ocr_mode == "nvidia":
            return self.nvidia.read_text(image, self._stop_event)

        easyocr_text = self.easyocr.read_text(image)
        if self.config.ocr_mode == "accurate":
            nvidia_text = self.nvidia.read_text(image, self._stop_event)
            return nvidia_text or easyocr_text

        if easyocr_text or self.config.ocr_mode == "easyocr":
            return easyocr_text

        return self.nvidia.read_text(image, self._stop_event)

    def _is_recent_duplicate(self, text: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.config.duplicate_text_window_seconds
        key = duplicate_key(text)

        expired = [
            submitted_key
            for submitted_key, submitted_at in self._recent_submissions.items()
            if submitted_at < cutoff
        ]
        for submitted_key in expired:
            del self._recent_submissions[submitted_key]

        return key in self._recent_submissions

    def _wait_for_submit_cooldown(self) -> None:
        elapsed = time.monotonic() - self._last_submitted_at
        remaining = self.config.min_seconds_between_submissions - elapsed
        if remaining > 0:
            self._stop_event.wait(remaining)

    def _paste_and_submit(self, text: str) -> None:
        with self._position_lock:
            input_box = self.input_box
            submit_button = self.submit_button
            play_button = self.play_button

        pyperclip.copy(text)
        pyautogui.click(*input_box)
        if self.config.paste_delay_seconds > 0:
            time.sleep(self.config.paste_delay_seconds)

        if self.config.clear_input_before_paste:
            pyautogui.hotkey("ctrl", "a")

        pyautogui.hotkey("ctrl", "v")
        if self.config.submit_delay_seconds > 0:
            time.sleep(self.config.submit_delay_seconds)

        pyautogui.click(*submit_button)

        if play_button and play_button != (0, 0):
            if self.config.play_delay_seconds > 0:
                time.sleep(self.config.play_delay_seconds)
            pyautogui.click(*play_button)
            print(f"Clicked Play button at {play_button[0]},{play_button[1]}")

    def _mark_submitted(self, text: str) -> None:
        now = time.monotonic()
        self._last_submitted_at = now
        self._recent_submissions[duplicate_key(text)] = now


def print_hotkeys(config: Config) -> None:
    print("F6 = Set input box to current mouse position")
    print("F7 = Set submit button to current mouse position")
    print("F10 = Set Play button to current mouse position")
    print("F11 = Set status banner point to current mouse position")
    print("F8 = Start bot")
    print("F9 = Stop bot")
    print("F12 = Print current mouse/config positions")
    print(f"OCR_MODE={config.ocr_mode}")
    print(f"CAPTURE_REGION={format_tuple(config.capture_region)}")


def make_dpi_aware() -> None:
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main() -> None:
    make_dpi_aware()
    load_dotenv()
    config = read_config()

    pyautogui.PAUSE = config.pyautogui_pause
    pyautogui.FAILSAFE = config.pyautogui_failsafe

    bot = ScreenOcrBot(config)
    keyboard.add_hotkey("F6", bot.calibrate_input_box)
    keyboard.add_hotkey("F7", bot.calibrate_submit_button)
    keyboard.add_hotkey("F10", bot.calibrate_play_button)
    keyboard.add_hotkey("F11", bot.calibrate_status_point)
    keyboard.add_hotkey("F8", bot.start)
    keyboard.add_hotkey("F9", bot.stop)
    keyboard.add_hotkey("F12", bot.print_positions)

    print_hotkeys(config)
    keyboard.wait()


if __name__ == "__main__":
    main()
