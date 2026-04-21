"""
Agent Tools — define and execute all tools available to the AI agent.
"""

import math
import json
import datetime
import requests
import urllib.request
import urllib.parse
import ssl
import re
import os
import sys
import webbrowser
import platform
import subprocess
import time
from typing import Any, Optional

# Try to import pyautogui, provide fallback if not available
try:
    import pyautogui
    # Configure pyautogui for safety
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.1  # Small pause between actions
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("Warning: pyautogui not installed. PC control features disabled.")

# Screen info cache
_screen_width = None
_screen_height = None


def get_screen_info():
    """Get screen size, cache it."""
    global _screen_width, _screen_height
    if _screen_width is None:
        _screen_width, _screen_height = pyautogui.size()
    return _screen_width, _screen_height


def get_smart_position(position_name="center"):
    """Get smart default positions on screen."""
    width, height = get_screen_info()

    positions = {
        "center": (width // 2, height // 2),
        "top-left": (width // 4, height // 4),
        "top-right": (width * 3 // 4, height // 4),
        "bottom-left": (width // 4, height * 3 // 4),
        "bottom-right": (width * 3 // 4, height * 3 // 4),
        "top-center": (width // 2, height // 6),
        "bottom-center": (width // 2, height * 5 // 6),
        "chrome-address": (width // 2, 80),
        "search-box": (width // 2, height // 3),
    }

    return positions.get(position_name, positions["center"])


def _clamp_coordinates(x, y):
    """Clamp x/y to screen bounds. Returns (clamped_x, clamped_y, was_clamped)."""
    if not PYAUTOGUI_AVAILABLE:
        return x, y, False
    width, height = get_screen_info()
    orig_x, orig_y = x, y
    x = max(0, min(int(x), width - 1))
    y = max(0, min(int(y), height - 1))
    was_clamped = (x != orig_x or y != orig_y)
    if was_clamped:
        print(f"Warning: Coordinates ({orig_x}, {orig_y}) out of bounds, clamped to ({x}, {y})")
    return x, y, was_clamped


# ── Tool Schemas ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate mathematical expressions. Supports +, -, *, /, **, sqrt, sin, cos, tan, log, abs, round.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression, e.g. '2 ** 10' or 'sqrt(144)'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_current_datetime",
        "description": "Get current date and time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for current information with source links using Google via SerpAPI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Cairo'"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "save_note",
        "description": "Save a note to a local file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Note content"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "read_notes",
        "description": "Read all saved notes.",
        "input_schema": {"type": "object", "properties": {}},
        "required": []
    },
    {
        "name": "unit_converter",
        "description": "Convert units (length, weight, temperature, speed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string"},
                "to_unit": {"type": "string"}
            },
            "required": ["value", "from_unit", "to_unit"]
        }
    },
    {
        "name": "pc_control",
        "description": "Full PC control: open links, mouse clicks (single/double/right), move, drag & drop, scroll, type text, press keys/hotkeys, screenshots, get screen info, run commands. Use for automating any desktop task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": [
                        "open_link", "click", "double_click", "right_click",
                        "move_mouse", "drag_to", "drag_drop", "scroll",
                        "type", "press_key", "hotkey", "screenshot",
                        "get_mouse_position", "get_screen_size",
                        "run_command", "sleep", "alert"
                    ]
                },
                "url": {"type": "string", "description": "URL to open"},
                "x": {"type": "number", "description": "X coordinate"},
                "y": {"type": "number", "description": "Y coordinate"},
                "start_x": {"type": "number", "description": "Start X for drag"},
                "start_y": {"type": "number", "description": "Start Y for drag"},
                "end_x": {"type": "number", "description": "End X for drag/drop"},
                "end_y": {"type": "number", "description": "End Y for drag/drop"},
                "clicks": {"type": "integer", "description": "Number of scroll clicks", "default": 3},
                "direction": {"type": "string", "description": "Scroll direction: up, down, left, right", "default": "down"},
                "text": {"type": "string", "description": "Text to type or command to run"},
                "key": {"type": "string", "description": "Single key to press"},
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple keys for hotkey combination (e.g., ['ctrl', 'c'])"
                },
                "button": {"type": "string", "description": "Mouse button: left, right, middle", "default": "left"},
                "duration": {"type": "number", "description": "Duration in seconds for drag or sleep", "default": 0.5},
                "message": {"type": "string", "description": "Message for alert popup"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "get_system_info",
        "description": "Get system information: OS type and Python version. Useful for debugging PC control tasks.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]


# ── Tool Handlers ───────────────────────────────────────────────────────────

def tool_calculator(expression: str) -> str:
    try:
        safe_globals = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_globals["abs"] = abs
        safe_globals["round"] = round
        result = eval(expression, {"__builtins__": {}}, safe_globals)
        return f"Result: {result}"
    except NameError as e:
        # Extract unrecognized name for a helpful hint
        bad_name = str(e).split("'")[1] if "'" in str(e) else str(e)
        return (
            f"❌ Unknown function or variable: '{bad_name}'. "
            f"Supported functions: sqrt, sin, cos, tan, log, log10, abs, round, ceil, floor. "
            f"Example: sqrt(144) not sqr(144)."
        )
    except SyntaxError:
        return (
            f"❌ Syntax error in expression: '{expression}'. "
            f"Use Python math syntax: 2**10, sqrt(144), 15*23. "
            f"Note: percent (%) is the modulo operator, not percentage."
        )
    except ZeroDivisionError:
        return "❌ Division by zero."
    except Exception as e:
        return (
            f"❌ Invalid expression: {e}. "
            f"Supported: +, -, *, /, **, sqrt, sin, cos, abs. "
            f"Example: sqrt(144), 25 * 4, 2 ** 10"
        )


def tool_get_current_datetime(timezone: str = None) -> str:
    now = datetime.datetime.now()
    return f"Current date: {now.strftime('%A, %B %d, %Y')}\nCurrent time: {now.strftime('%H:%M:%S')}"


def tool_web_search(query: str, num_results: int = 5) -> str:
    serpapi_key = os.getenv("SERPAPI_KEY", "")

    if serpapi_key:
        try:
            return _search_serpapi(query, serpapi_key, num_results)
        except Exception as e:
            print(f"SerpAPI failed: {e}, trying DuckDuckGo fallback...")

    try:
        result = _search_duckduckgo(query, num_results)
        if result and "No results found" not in result:
            return result
        # DuckDuckGo returned no results
        return (
            f"No results found for '{query}'. "
            f"Try rephrasing your query, using fewer keywords, or searching in English."
        )
    except Exception as e:
        return (
            f"⚠️ Search is currently unavailable (error: {str(e)[:100]}). "
            f"Please check your internet connection and try again later. "
            f"If you have a SerpAPI key, set SERPAPI_KEY in your .env for more reliable searches."
        )


def _search_serpapi(query: str, api_key: str, num_results: int) -> str:
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": num_results,
        "hl": "en"
    }

    response = requests.get(url, params=params, timeout=15)
    data = response.json()

    if data.get("error"):
        raise Exception(data["error"])

    results = []
    for result in data.get("organic_results", [])[:num_results]:
        title = result.get("title", "No title")
        link = result.get("link", "")
        snippet = result.get("snippet", "No description")
        results.append(f"**{title}**\n{snippet}\n🔗 {link}")

    if results:
        return f"Search results for '{query}':\n\n" + "\n\n".join(results)

    raise Exception("No results from SerpAPI")


def _search_duckduckgo(query: str, num_results: int) -> str:
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    req = urllib.request.Request(url, headers=headers)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
        html = response.read().decode('utf-8', errors='ignore')

    results = []
    link_pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    snippet_pattern = r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>'

    links = re.findall(link_pattern, html, re.DOTALL)
    snippets = re.findall(snippet_pattern, html, re.DOTALL)

    for i, (href, title) in enumerate(links[:num_results]):
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        clean_title = re.sub(r'\s+', ' ', clean_title)

        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
            snippet = re.sub(r'\s+', ' ', snippet)
            snippet = snippet[:200]

        clean_url = href.strip()
        if '/l/?' in clean_url:
            match = re.search(r'uddg=([^&]+)', clean_url)
            if match:
                clean_url = urllib.parse.unquote(match.group(1))

        if clean_title and clean_title.lower() != "duckduckgo":
            results.append(f"**{clean_title}**\n{snippet}\n🔗 {clean_url}")

    if results:
        return f"Search results for '{query}':\n\n" + "\n\n".join(results)

    return f"No results found for '{query}'."


def tool_get_weather(city: str) -> str:
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_resp = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10)
        geo_data = geo_resp.json()

        if not geo_data.get("results"):
            return f"City '{city}' not found."

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        name = loc.get("name", city)
        country = loc.get("country", "")

        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
        }
        w_resp = requests.get(weather_url, params=params, timeout=10)
        w_data = w_resp.json()

        cw = w_data.get("current_weather", {})
        temp = cw.get("temperature", "N/A")
        wind = cw.get("windspeed", "N/A")
        code = cw.get("weathercode", 0)

        weather_desc = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 61: "Light rain",
            71: "Light snow", 80: "Rain showers", 95: "Thunderstorm"
        }.get(code, "Unknown conditions")

        return (
            f"Weather in {name}, {country}:\n"
            f"🌡️ Temperature: {temp}°C\n"
            f"💨 Wind speed: {wind} km/h\n"
            f"☁️ Conditions: {weather_desc}"
        )

    except Exception as e:
        return f"Weather error: {e}"


def tool_save_note(title: str, content: str) -> str:
    notes_file = "notes.json"
    try:
        notes = {}
        if os.path.exists(notes_file):
            with open(notes_file, "r") as f:
                notes = json.load(f)

        timestamp = datetime.datetime.now().isoformat()
        notes[title] = {"content": content, "saved_at": timestamp}

        with open(notes_file, "w") as f:
            json.dump(notes, f, indent=2)

        return f"✅ Note '{title}' saved."
    except Exception as e:
        return f"Error saving note: {e}"


def tool_read_notes() -> str:
    notes_file = "notes.json"
    try:
        if not os.path.exists(notes_file):
            return "No notes saved yet."

        with open(notes_file, "r") as f:
            notes = json.load(f)

        if not notes:
            return "No notes saved yet."

        output = []
        for title, data in notes.items():
            output.append(f"📝 **{title}** (saved {data['saved_at'][:10]})\n{data['content']}")

        return "\n\n".join(output)
    except Exception as e:
        return f"Error reading notes: {e}"


def tool_unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    try:
        to_meters = {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001,
                     "miles": 1609.34, "mile": 1609.34, "ft": 0.3048,
                     "feet": 0.3048, "inch": 0.0254, "inches": 0.0254}
        to_kg = {"kg": 1, "g": 0.001, "mg": 1e-6, "lb": 0.453592,
                 "lbs": 0.453592, "pounds": 0.453592, "oz": 0.0283495}
        to_mps = {"m/s": 1, "km/h": 1/3.6, "kph": 1/3.6, "mph": 0.44704}

        if fu in ("celsius", "c") and tu in ("fahrenheit", "f"):
            result = value * 9/5 + 32
        elif fu in ("fahrenheit", "f") and tu in ("celsius", "c"):
            result = (value - 32) * 5/9
        elif fu in to_meters and tu in to_meters:
            result = value * to_meters[fu] / to_meters[tu]
        elif fu in to_kg and tu in to_kg:
            result = value * to_kg[fu] / to_kg[tu]
        elif fu in to_mps and tu in to_mps:
            result = value * to_mps[fu] / to_mps[tu]
        else:
            return f"❌ Unsupported conversion: {from_unit} → {to_unit}"

        return f"✅ {value} {from_unit} = {round(result, 4)} {to_unit}"

    except Exception as e:
        return f"Conversion error: {e}"


def tool_get_system_info() -> str:
    """Return OS type and Python version for debugging."""
    os_name = platform.system()
    os_version = platform.version()
    os_release = platform.release()
    python_version = sys.version.split()[0]
    machine = platform.machine()
    return (
        f"🖥️ OS: {os_name} {os_release} ({os_version})\n"
        f"🐍 Python: {python_version}\n"
        f"⚙️ Architecture: {machine}\n"
        f"🖱️ PyAutoGUI: {'Available' if PYAUTOGUI_AVAILABLE else 'Not installed'}"
    )


def tool_pc_control(
    action: str,
    url: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    start_x: Optional[float] = None,
    start_y: Optional[float] = None,
    end_x: Optional[float] = None,
    end_y: Optional[float] = None,
    clicks: int = 3,
    direction: str = "down",
    text: Optional[str] = None,
    key: Optional[str] = None,
    keys: Optional[list] = None,
    button: str = "left",
    duration: float = 0.5,
    message: Optional[str] = None
) -> str:
    """
    Full PC control with mouse, keyboard, screen, and system commands.
    """

    mouse_actions = ["click", "double_click", "right_click", "move_mouse",
                     "drag_to", "drag_drop", "scroll", "get_mouse_position", "get_screen_size"]

    if action in mouse_actions and not PYAUTOGUI_AVAILABLE:
        return "❌ PC control requires pyautogui. Install: pip install pyautogui"

    # Smart defaults for coordinates
    if action in ["click", "double_click", "right_click", "move_mouse"]:
        if x is None or y is None:
            x, y = get_smart_position("center")

    # Clamp coordinates to screen bounds for all mouse actions
    clamp_actions = ["click", "double_click", "right_click", "move_mouse", "drag_to"]
    clamp_note = ""
    if action in clamp_actions and x is not None and y is not None and PYAUTOGUI_AVAILABLE:
        x, y, was_clamped = _clamp_coordinates(x, y)
        if was_clamped:
            clamp_note = f" (coordinates clamped to screen bounds)"

    try:
        if action == "open_link":
            if not url:
                return "❌ Error: URL required for open_link"
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
            return f"✅ Opened link: {url}"

        elif action == "click":
            pyautogui.click(x, y, button=button)
            return f"✅ Clicked {button} button at ({x}, {y}){clamp_note}"

        elif action == "double_click":
            pyautogui.doubleClick(x, y)
            return f"✅ Double-clicked at ({x}, {y}){clamp_note}"

        elif action == "right_click":
            pyautogui.rightClick(x, y)
            return f"✅ Right-clicked at ({x}, {y}){clamp_note}"

        elif action == "move_mouse":
            pyautogui.moveTo(x, y, duration=duration)
            return f"✅ Moved mouse to ({x}, {y}){clamp_note}"

        elif action == "drag_to":
            pyautogui.dragTo(x, y, duration=duration, button=button)
            return f"✅ Dragged {button} button to ({x}, {y}){clamp_note}"

        elif action == "drag_drop":
            if start_x is None or start_y is None or end_x is None or end_y is None:
                return "❌ Error: start_x, start_y, end_x, end_y required"
            if PYAUTOGUI_AVAILABLE:
                start_x, start_y, _ = _clamp_coordinates(start_x, start_y)
                end_x, end_y, _ = _clamp_coordinates(end_x, end_y)
            pyautogui.moveTo(start_x, start_y, duration=0.2)
            pyautogui.mouseDown(button=button)
            pyautogui.moveTo(end_x, end_y, duration=duration)
            pyautogui.mouseUp(button=button)
            return f"✅ Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"

        elif action == "scroll":
            scroll_amount = clicks if direction in ["down", "right"] else -clicks
            if direction in ["up", "down"]:
                pyautogui.scroll(scroll_amount)
            else:
                pyautogui.hscroll(scroll_amount)
            return f"✅ Scrolled {direction} {abs(clicks)} clicks"

        elif action == "type":
            if not text:
                return "❌ Error: text required"
            pyautogui.typewrite(text, interval=0.01)
            return f"✅ Typed: {text}"

        elif action == "press_key":
            if not key:
                return "❌ Error: key required"
            pyautogui.press(key)
            return f"✅ Pressed key: {key}"

        elif action == "hotkey":
            if not keys or len(keys) < 2:
                return "❌ Error: at least 2 keys required"
            pyautogui.hotkey(*keys)
            return f"✅ Pressed hotkey: {' + '.join(keys)}"

        elif action == "screenshot":
            screenshot = pyautogui.screenshot()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            screenshot.save(filename)
            return f"✅ Screenshot saved: {filename}"

        elif action == "get_mouse_position":
            x, y = pyautogui.position()
            return f"🖱️ Mouse: ({x}, {y})"

        elif action == "get_screen_size":
            width, height = pyautogui.size()
            return f"🖥️ Screen: {width}x{height}"

        elif action == "run_command":
            if not text:
                return "❌ Error: command required"
            result = subprocess.run(text, shell=True, capture_output=True, text=True)
            output = result.stdout if result.stdout else "No output"
            return f"✅ Command executed:\n{output[:500]}"

        elif action == "sleep":
            time.sleep(duration)
            return f"⏸️ Slept {duration}s"

        elif action == "alert":
            if not message:
                message = "Alert from AI"
            pyautogui.alert(message, "AI Agent")
            return f"✅ Alert: {message}"

        else:
            return f"❌ Unknown action: {action}"

    except Exception as e:
        return f"❌ Error: {str(e)}"


# ── Dispatch ─────────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "calculator": lambda inp: tool_calculator(inp["expression"]),
    "get_current_datetime": lambda inp: tool_get_current_datetime(),
    "web_search": lambda inp: tool_web_search(inp["query"]),
    "get_weather": lambda inp: tool_get_weather(inp["city"]),
    "save_note": lambda inp: tool_save_note(inp["title"], inp["content"]),
    "read_notes": lambda inp: tool_read_notes(),
    "unit_converter": lambda inp: tool_unit_converter(inp["value"], inp["from_unit"], inp["to_unit"]),
    "get_system_info": lambda inp: tool_get_system_info(),
    "pc_control": lambda inp: tool_pc_control(
        inp["action"],
        inp.get("url"),
        inp.get("x"),
        inp.get("y"),
        inp.get("start_x"),
        inp.get("start_y"),
        inp.get("end_x"),
        inp.get("end_y"),
        inp.get("clicks", 3),
        inp.get("direction", "down"),
        inp.get("text"),
        inp.get("key"),
        inp.get("keys"),
        inp.get("button", "left"),
        inp.get("duration", 0.5),
        inp.get("message")
    ),
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"
    try:
        return handler(tool_input)
    except Exception as e:
        return f"Tool '{tool_name}' failed: {e}"