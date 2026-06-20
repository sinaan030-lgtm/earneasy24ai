from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import threading
import time
import traceback
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
DEFAULT_STATUS_POINT = (0, 0)

DEFAULT_NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-nano-vl-8b-v1"


@dataclass(frozen=True)
class Config:
    capture_region: tuple[int, int, int, int]
    loop_delay_seconds: float
    change_cooldown_seconds: float
    post_change_settle_seconds: float
    process_initial_frame: bool
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
    clear_input_before_paste: bool
    pyautogui_pause: float
    pyautogui_failsafe: bool
    min_captcha_length: int
    max_captcha_length: int
    character_replacements: dict[str, str]
    status_point: tuple[int, int]
    double_check: bool


def load_dotenv(force: bool = False) -> None:
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

        if key:
            if force or key not in os.environ:
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



def read_config() -> Config:
    load_dotenv(force=True)
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
        change_cooldown_seconds=env_float("CHANGE_COOLDOWN_SECONDS", 3.0),
        post_change_settle_seconds=env_float("POST_CHANGE_SETTLE_SECONDS", 0.15),
        process_initial_frame=env_bool("PROCESS_INITIAL_FRAME", True),
        nvidia_api_url=env_str("NVIDIA_API_URL", DEFAULT_NVIDIA_API_URL),
        nvidia_model=env_str("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL),
        nvidia_api_key=env_str("NVIDIA_API_KEY", env_str("NIM_API_KEY")),
        ai_timeout_seconds=env_float("AI_TIMEOUT_SECONDS", 60.0),
        ai_connect_timeout_seconds=env_float("AI_CONNECT_TIMEOUT_SECONDS", 5.0),
        ai_max_tokens=env_int("AI_MAX_TOKENS", 512),
        ai_fallback_min_interval_seconds=env_float(
            "AI_FALLBACK_MIN_INTERVAL_SECONDS",
            0.5,
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
        clear_input_before_paste=env_bool("CLEAR_INPUT_BEFORE_PASTE", True),
        pyautogui_pause=env_float("PYAUTOGUI_PAUSE", 0.02),
        pyautogui_failsafe=env_bool("PYAUTOGUI_FAILSAFE", True),
        min_captcha_length=env_int("MIN_CAPTCHA_LENGTH", 6),
        max_captcha_length=env_int("MAX_CAPTCHA_LENGTH", 20),
        character_replacements=replacements,
        status_point=parse_int_tuple("STATUS_POINT", 2, DEFAULT_STATUS_POINT),
        double_check=env_bool("DOUBLE_CHECK", True),
    )


def format_tuple(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def save_to_env(updates: dict[str, str]) -> None:
    """Write or update key=value pairs in the .env file without restarting."""
    env_path = Path(__file__).with_name(".env")
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    existing_keys: dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _ = stripped.split("=", 1)
            existing_keys[key.strip()] = idx

    for key, val in updates.items():
        if key in existing_keys:
            lines[existing_keys[key]] = f"{key}={val}\n"
        else:
            lines.append(f"{key}={val}\n")

    env_path.write_text("".join(lines), encoding="utf-8")
    # Reflect changes immediately in os.environ so read_config() picks them up
    for key, val in updates.items():
        os.environ[key] = val


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

    # Support Chain-of-Thought output: search for "CAPTCHA: <value>" (case-insensitive)
    match = re.search(r"CAPTCHA\s*:\s*([^\r\n]+)", text, re.IGNORECASE)
    if match:
        # Successfully extracted via CAPTCHA: prefix — preserve the value as-is
        # (do NOT strip underscores or other chars that are valid CAPTCHA characters)
        text = match.group(1).strip().strip("\"'` ")
    else:
        # No structured prefix — treat as raw model output and remove markdown
        # formatting artifacts (bold **text**, italic *text*, __underline__, etc.)
        text = text.replace("**", "").replace("__", "").replace("*", "")

        # Strip common code blocks
        text = re.sub(r"^```(?:text)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

        # Strip common answer prefixes: "Answer:", "Text:", "The captcha is:", etc.
        prefix_pattern = r"^(?:the\s+)?(?:captcha|answer|text|value|solution|challenge|result)(?:\s+is)?\s*[:=-]\s*"
        text = re.sub(prefix_pattern, "", text, flags=re.IGNORECASE).strip()

        # Strip surrounding quotes/backticks
        text = text.strip("\"'` ")

    lower_text = text.lower()
    if any(phrase in lower_text for phrase in [
        "sorry", "cannot read", "unable to", "don't see",
        "no text", "clear text", "i see", "loading spinner", "blinking cursor",
    ]):
        return ""

    # Reject literal template placeholders the AI might echo from the prompt
    if text in {"<answer>", "<exact_characters>", "<exact_text>", "<value>",
                "<text>", "VALUE", "value", "[answer]", "[value]"}:
        return ""

    # Strip trailing punctuation for the none-check (handles 'NONE.' / 'NONE!' etc.)
    stripped_lower = lower_text.rstrip(".,!?;:")
    if stripped_lower in {"none", "no text", "no visible text", "n/a", ""}:
        return ""

    # Strip trailing punctuation commonly added by LLMs
    text = text.rstrip(".,!?;:")

    return text


def clean_detected_text(text: str, replacements: dict[str, str] = None) -> str:
    text = clean_model_output(text)
    if replacements:
        for old, new in replacements.items():
            text = text.replace(old, new)
    text = text.replace("\r", "").replace("\n", "")
    text = "".join(text.split())
    # Strip non-printable-ASCII characters (e.g. £, accented letters, control chars)
    text = "".join(ch for ch in text if 32 <= ord(ch) <= 126)
    return text



def duplicate_key(text: str) -> str:
    return " ".join(text.casefold().split())


def _preprocess_for_ai(image: Any, mode: int = 0) -> Any:
    """Preprocess the CAPTCHA image before sending to the AI model.

    Three distinct pipelines give meaningfully different views of the same
    CAPTCHA, improving consensus quality when 3 reads are compared:

        mode=0 (default): 2× LANCZOS upscale — baseline high-quality view.
        mode=1: 2× upscale + gentle contrast boost (1.4×) — makes chars bolder
                without clipping or distorting shapes.
        mode=2: 2× upscale + slight brightness reduction (0.85×) — makes dark
                characters on a light background stand out more.
    """
    try:
        from PIL import Image, ImageEnhance

        # Always start from RGB so operations are consistent
        img = image.convert("RGB")
        w, h = img.size

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.ANTIALIAS  # type: ignore[attr-defined]

        # Common first step: 2× LANCZOS upscale for all modes
        img = img.resize((w * 2, h * 2), resample)

        if mode == 1:
            # Gentle contrast boost — makes faint/thin strokes stand out without
            # clipping pixel values or distorting character shapes
            img = ImageEnhance.Contrast(img).enhance(1.4)
        elif mode == 2:
            # Slight brightness reduction — dark chars on light bg become more
            # distinct; does not touch hue or saturation so colour info is kept
            img = ImageEnhance.Brightness(img).enhance(0.85)
        # else mode=0: plain 2× LANCZOS upscale (already done above)

        return img
    except Exception:
        # If preprocessing fails for any reason, return original image
        return image


# Three distinct prompting strategies used in parallel reads.
# Different angles on the same problem create genuine diversity even at temperature=0.
_PROMPT_VARIANTS = (
    # Variant 0: Detailed with full disambiguation hints
    (
        "You are a CAPTCHA transcription engine. Your ONLY job is to read the exact characters shown in this CAPTCHA image.\n"
        "\n"
        "OUTPUT FORMAT (mandatory): CAPTCHA: <exact_characters>\n"
        "If the image is unreadable: CAPTCHA: NONE\n"
        "\n"
        "RULES:\n"
        "1. Copy every visible character exactly as shown, left to right. This includes letters, digits, AND all special characters (%, =, @, #, $, !, +, -, etc.).\n"
        "2. Ignore decorations only: strike-through lines, grid lines, and background noise are NOT part of the CAPTCHA answer.\n"
        "3. Case-sensitive: uppercase A-Z and lowercase a-z are DIFFERENT — preserve exactly as shown.\n"
        "4. Common look-alike pairs — choose the one that visually matches the pixel shape:\n"
        "   - 0 (zero, round) vs O (letter O, slightly taller oval)\n"
        "   - 1 (one, thin vertical) vs l (lowercase L) vs I (capital i)\n"
        "   - 5 (five, angular top) vs S (letter S, curved)\n"
        "   - 2 (two) vs Z (letter Z)\n"
        "   - 9 (nine) vs g (letter g) vs q (letter q)\n"
        "   - 8 (eight) vs B (letter B)\n"
        "   - 6 (six) vs b (letter b)\n"
        "   - rn (two letters r+n) vs m (one letter m)\n"
        "   - cl (two letters c+l) vs d (one letter d)\n"
        "5. Do NOT add explanations, steps, or any text beyond the CAPTCHA value itself.\n"
        "6. Output ONLY the single line: CAPTCHA: <value>"
    ),
    # Variant 1: Minimal and direct (pure vision, no priming hints)
    (
        "Look at this CAPTCHA image and output exactly the text you see.\n"
        "Format: CAPTCHA: <text>\n"
        "Rules: preserve exact case, include every symbol visible, do not add explanations.\n"
        "Output ONLY: CAPTCHA: <text>"
    ),
    # Variant 2: Case and special-character focused
    (
        "Transcribe this CAPTCHA image character by character, left to right.\n"
        "Format: CAPTCHA: <exact_text>\n"
        "Critical:\n"
        "- Exact case required: lowercase a-z and uppercase A-Z are DIFFERENT characters\n"
        "- Include every special symbol shown (%, =, @, #, $, !, +, etc.)\n"
        "- Distinguish carefully: 0 vs O, 1 vs l vs I, 5 vs S, 2 vs Z, 8 vs B\n"
        "- Ignore background lines/noise — output ONLY the actual CAPTCHA text\n"
        "Output ONLY: CAPTCHA: <exact_text>"
    ),
)


class NvidiaVisionClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._last_call_at = 0.0
        self._missing_key_reported = False
        self._consecutive_network_failures = 0
        self._network_backoff_until = 0.0
        self._last_failure_at = 0.0
        self._last_backoff_warned_at = 0.0
        self._lock = threading.Lock()

    def read_text(
        self,
        image: Any,
        stop_event: threading.Event | None = None,
        bypass_cooldown: bool = False,
        prompt_variant: int = 0,
    ) -> str:
        if not self.config.nvidia_api_key:
            if not self._missing_key_reported:
                print("NVIDIA fallback unavailable: NVIDIA_API_KEY is not set")
                self._missing_key_reported = True
            return ""

        # Check circuit breaker / backoff
        now = time.monotonic()
        with self._lock:
            if now < self._network_backoff_until:
                if now - self._last_backoff_warned_at > 15.0:
                    remaining = self._network_backoff_until - now
                    print(f"[NVIDIA] Circuit breaker active (network down?). Skipping API calls for next {remaining:.1f}s.")
                    self._last_backoff_warned_at = now
                return ""

        if not bypass_cooldown:
            now = time.monotonic()
            elapsed = now - self._last_call_at
            if elapsed < self.config.ai_fallback_min_interval_seconds:
                remaining = self.config.ai_fallback_min_interval_seconds - elapsed
                if stop_event is not None and stop_event.wait(remaining):
                    return ""
                if stop_event is None:
                    time.sleep(remaining)

        self._last_call_at = time.monotonic()
        prompt_text = _PROMPT_VARIANTS[prompt_variant % len(_PROMPT_VARIANTS)]
        payload = {
            "model": self.config.nvidia_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text,
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_png_data_url(
                                _preprocess_for_ai(image)
                            )},
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": self.config.ai_max_tokens,
            "stream": False,
        }

        success = False
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
                result = clean_model_output(extract_message_content(data))
                success = True
                
                # Reset circuit breaker on successful API call
                with self._lock:
                    if self._consecutive_network_failures > 0:
                        print("[NVIDIA] API connection recovered. Resetting circuit breaker.")
                    self._consecutive_network_failures = 0
                    self._network_backoff_until = 0.0
                return result
            except Exception as exc:
                # We only print individual attempt failures if the circuit breaker hasn't kicked in
                print(f"[NVIDIA] Attempt {attempt} failed: {exc}")
                if attempt < 3:
                    if stop_event is not None and stop_event.wait(1.0):
                        return ""
                    elif stop_event is None:
                        time.sleep(1.0)

        # If all 3 attempts failed, handle circuit breaker logic
        if not success:
            with self._lock:
                now_fail = time.monotonic()
                # Treat parallel failures within 1.5 seconds as a single failure event
                if now_fail - self._last_failure_at > 1.5:
                    self._consecutive_network_failures += 1
                    self._last_failure_at = now_fail
                    
                    if self._consecutive_network_failures == 1:
                        delay = 2.0
                    elif self._consecutive_network_failures == 2:
                        delay = 5.0
                    elif self._consecutive_network_failures == 3:
                        delay = 15.0
                    elif self._consecutive_network_failures == 4:
                        delay = 30.0
                    else:
                        delay = 60.0
                    
                    self._network_backoff_until = now_fail + delay
                    print(f"[NVIDIA] Fallback failed. Consecutive network failure count: {self._consecutive_network_failures}. Backing off for {delay:.1f}s.")
            
        return ""

    def _auth_header(self) -> str:
        key = self.config.nvidia_api_key.strip()
        if key.lower().startswith("bearer "):
            return key
        return f"Bearer {key}"


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
        self.status_point = parse_int_tuple(
            "STATUS_POINT",
            2,
            DEFAULT_STATUS_POINT,
        )
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

        print("Bot started (NVIDIA vision mode)")

    def stop(self) -> None:
        self._stop_event.set()
        print("Bot stopped")

    def calibrate_input_box(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.input_box = (position.x, position.y)
        save_to_env({"INPUT_BOX": f"{position.x},{position.y}"})
        print(f"Input box set to {position.x},{position.y}")

    def calibrate_submit_button(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.submit_button = (position.x, position.y)
        save_to_env({"SUBMIT_BUTTON": f"{position.x},{position.y}"})
        print(f"Submit button set to {position.x},{position.y}")

    def calibrate_status_point(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            self.status_point = (position.x, position.y)
        save_to_env({"STATUS_POINT": f"{position.x},{position.y}"})
        print(f"Status point set to {position.x},{position.y}")

    def set_input_box(self, pos: tuple[int, int]) -> None:
        with self._position_lock:
            self.input_box = pos

    def set_submit_button(self, pos: tuple[int, int]) -> None:
        with self._position_lock:
            self.submit_button = pos

    def set_status_point(self, pos: tuple[int, int]) -> None:
        with self._position_lock:
            self.status_point = pos

    def update_config(self, config: Config) -> None:
        with self._state_lock:
            self.config = config
            self.nvidia.config = config

    def print_positions(self) -> None:
        position = pyautogui.position()
        with self._position_lock:
            input_box = self.input_box
            submit_button = self.submit_button
            status_point = self.status_point

        print(f"Mouse position: {position.x},{position.y}")
        print(f"CAPTURE_REGION={format_tuple(self.config.capture_region)}")
        print(f"INPUT_BOX={format_tuple(input_box)}")
        print(f"SUBMIT_BUTTON={format_tuple(submit_button)}")
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
                print(traceback.format_exc())

            self._stop_event.wait(self.config.loop_delay_seconds)

    def _step(self) -> None:
        image = capture_screen(self.config)

        current_hash = frame_hash(image)
        if self._last_frame_hash and current_hash == self._last_frame_hash:
            return  # Frame unchanged — nothing to do

        # New frame detected. Wait briefly so that rapid loading/transition
        # frames are skipped, then re-capture the most recent stable view.
        # We always proceed after the wait — never loop-bail — to avoid an
        # infinite defer when the CAPTCHA region has continuous animation.
        settle = self.config.post_change_settle_seconds
        if settle > 0 and not self._stop_event.wait(settle):
            image = capture_screen(self.config)
            current_hash = frame_hash(image)

        self._last_frame_hash = current_hash

        detected_text = self._read_and_confirm_text(image)
        # _read_and_confirm_text already returns a cleaned string in double_check
        # mode; apply cleaning again to handle single-check mode or edge cases.
        cleaned_text = clean_detected_text(detected_text, self.config.character_replacements)

        if not cleaned_text:
            # Reset hash so the same frame is retried on the next loop tick
            self._last_frame_hash = None
            time.sleep(0.5)
            return

        if len(cleaned_text) < self.config.min_captcha_length:
            self._last_frame_hash = None
            time.sleep(0.5)
            return

        if len(cleaned_text) > self.config.max_captcha_length:
            self._last_frame_hash = None
            time.sleep(0.5)
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

    def _read_and_confirm_text(self, image: Any) -> str:
        """Read CAPTCHA text using NVIDIA vision API with parallel verification for speed and accuracy.

        Three distinct image preprocessing pipelines (see _preprocess_for_ai) are sent
        in parallel. A majority-vote with similarity-based tiebreaker selects the best result.
        """
        import concurrent.futures

        if not self.config.double_check:
            return self.nvidia.read_text(image, self._stop_event)

        # Three meaningfully different preprocessings of the same image
        # mode=0: 2× LANCZOS, mode=1: 3× + contrast, mode=2: 2× + grayscale + sharpen
        preprocess_modes = [0, 1, 2]

        def _read_with_mode(mode: int) -> str:
            try:
                preprocessed = _preprocess_for_ai(image, mode)
            except Exception:
                preprocessed = image
            # Each mode uses a different prompt variant to create genuine
            # diversity in model responses, even at temperature=0
            return self.nvidia.read_text(
                preprocessed,
                self._stop_event,
                bypass_cooldown=True,
                prompt_variant=mode,
            )

        # Run all 3 reads in parallel
        results = ["", "", ""]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_read_with_mode, mode): idx
                for idx, mode in enumerate(preprocess_modes)
            }
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"[Confirm] Parallel read error (mode {preprocess_modes[idx]}): {e}")

        # Update last call time so the next loop step respects the cooldown
        self.nvidia._last_call_at = time.monotonic()

        text1, text2, text3 = results[0], results[1], results[2]

        # Clean all results for comparison
        cleaned1 = clean_detected_text(text1, self.config.character_replacements) if text1 else ""
        cleaned2 = clean_detected_text(text2, self.config.character_replacements) if text2 else ""
        cleaned3 = clean_detected_text(text3, self.config.character_replacements) if text3 else ""

        # --- Stage 1: Exact 2-of-3 majority vote ---
        if cleaned1 and cleaned1 == cleaned2:
            print(f"[Confirm] OK: '{cleaned1}' (modes 0+1 agree)")
            return cleaned1
        if cleaned1 and cleaned1 == cleaned3:
            print(f"[Confirm] OK: '{cleaned1}' (modes 0+2 agree)")
            return cleaned1
        if cleaned2 and cleaned2 == cleaned3:
            print(f"[Confirm] OK: '{cleaned2}' (modes 1+2 agree)")
            return cleaned2

        # --- Stage 2: Character-level majority vote then Levenshtein tiebreaker ---
        # When all three disagree, attempt position-by-position voting first
        # (only possible when strings share the same length), then fall back to
        # the Levenshtein similarity tiebreaker.
        candidates = [(cleaned1, text1), (cleaned2, text2), (cleaned3, text3)]
        non_empty = [(c, r) for c, r in candidates if c]

        if not non_empty:
            print(f"[Confirm] Mismatch: '{cleaned1}' vs '{cleaned2}' vs '{cleaned3}' —- Best guess: ''")
            return ""

        if len(non_empty) == 1:
            winner_cleaned, winner_raw = non_empty[0]
            print(f"[Confirm] Mismatch: '{cleaned1}' vs '{cleaned2}' vs '{cleaned3}' —- Best guess: '{winner_cleaned}'")
            return winner_cleaned

        # Try character-level per-position majority vote when all 3 are same length
        if len(non_empty) == 3 and len(cleaned1) == len(cleaned2) == len(cleaned3):
            voted = []
            for c1, c2, c3 in zip(cleaned1, cleaned2, cleaned3):
                if c1 == c2:
                    voted.append(c1)   # modes 0+1 agree at this position
                elif c1 == c3:
                    voted.append(c1)   # modes 0+2 agree at this position
                elif c2 == c3:
                    voted.append(c2)   # modes 1+2 agree at this position
                else:
                    # All 3 differ: use variant-0 (most detailed prompt) as tie
                    voted.append(c1)
            winner_cleaned = "".join(voted)
            print(
                f"[Confirm] Mismatch (char-vote): '{cleaned1}' vs '{cleaned2}' vs '{cleaned3}' "
                f"—- Best guess: '{winner_cleaned}'"
            )
            return winner_cleaned

        def _levenshtein(a: str, b: str) -> int:
            """Simple O(mn) Levenshtein distance."""
            if a == b:
                return 0
            if not a:
                return len(b)
            if not b:
                return len(a)
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a):
                curr = [i + 1]
                for j, cb in enumerate(b):
                    curr.append(min(
                        prev[j + 1] + 1,   # deletion
                        curr[j] + 1,       # insertion
                        prev[j] + (0 if ca == cb else 1),  # substitution
                    ))
                prev = curr
            return prev[-1]

        def _similarity_score(candidate: str, others: list[str]) -> int:
            """Lower total Levenshtein distance to all others = better score."""
            return sum(_levenshtein(candidate, o) for o in others)

        # Score each non-empty candidate against all three candidates
        all_cleaned = [cleaned1, cleaned2, cleaned3]
        scored = [
            (_similarity_score(c, all_cleaned), len(c), c, r)
            for c, r in non_empty
        ]
        # Sort: lowest distance first, then longest string as tiebreaker
        scored.sort(key=lambda x: (x[0], -x[1]))
        winner_cleaned = scored[0][2]

        print(
            f"[Confirm] Mismatch: '{cleaned1}' vs '{cleaned2}' vs '{cleaned3}' "
            f"—- Best guess: '{winner_cleaned}'"
        )
        return winner_cleaned

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

        # Ensure the text is properly copied to the clipboard
        copy_success = False
        for attempt in range(5):
            try:
                pyperclip.copy(text)
                if pyperclip.paste() == text:
                    copy_success = True
                    break
            except Exception as e:
                print(f"[Warning] Clipboard copy failed, retrying (attempt {attempt + 1}/5): {e}")
            time.sleep(0.05)
        else:
            print("[Clipboard] Warning: Could not confirm clipboard copy after retries")

        # Focus the input field
        pyautogui.click(*input_box)
        # Give emulator/OS time to focus window and input field
        time.sleep(max(0.2, self.config.paste_delay_seconds))

        # Clear existing text reliably
        if self.config.clear_input_before_paste:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
            time.sleep(0.1)

        # Paste the text (retry up to 3 times if paste fails)
        for _paste_attempt in range(3):
            try:
                pyautogui.hotkey("ctrl", "v")
                break
            except Exception as exc:
                print(f"[Clipboard] Paste attempt {_paste_attempt + 1} failed: {exc}")
                time.sleep(0.15)
        # Give emulator time to process paste and draw characters
        time.sleep(max(0.2, self.config.submit_delay_seconds))

        # Click submit
        pyautogui.click(*submit_button)

    def _mark_submitted(self, text: str) -> None:
        now = time.monotonic()
        self._last_submitted_at = now
        self._recent_submissions[duplicate_key(text)] = now


def print_hotkeys(config: Config) -> None:
    print("F6 = Set input box to current mouse position")
    print("F7 = Set submit button to current mouse position")
    print("F11 = Set status banner point to current mouse position")
    print("F8 = Start bot")
    print("F9 = Stop bot")
    print("F12 = Print current mouse/config positions")
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
    keyboard.add_hotkey("F11", bot.calibrate_status_point)
    keyboard.add_hotkey("F8", bot.start)
    keyboard.add_hotkey("F9", bot.stop)
    keyboard.add_hotkey("F12", bot.print_positions)

    print_hotkeys(config)
    keyboard.wait()


if __name__ == "__main__":
    main()
