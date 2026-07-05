"""
pexels_video_downloader.py
---------------------------
Single-file Pexels Video Dataset Downloader.

A desktop app (PySide6) that downloads stock videos from the Pexels API
and organizes them into category folders, with duplicate protection,
smart resume, multithreaded downloading, and a responsive GUI.

Run with:
    pip install PySide6 requests
    python pexels_video_downloader.py
"""

import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# ============================================================================
# CONFIG
# ============================================================================

# 15 cheating-story categories (folder names shown in the UI / on disk)
CATEGORIES: List[str] = [
    "Wife Cheating on Husband",
    "Husband Cheating on Wife",
    "Boyfriend Cheating",
    "Girlfriend Cheating",
    "Cheating with Best Friend",
    "Cheating with Siblings Partner",
    "Online Dating App Cheating",
    "Long Distance Relationship Cheating",
    "Cheating Before Wedding",
    "Cheating During Pregnancy",
    "Cheating with Ex",
    "Workplace Cheating",
    "Cheating Caught on Camera or Chat",
    "Revenge Cheating",
    "Cheating Confession Stories",
]

# Pexels has no clips literally tagged "wife cheating on husband" etc.
# Each category is mapped to a real, neutral, searchable Pexels query that
# returns visually fitting b-roll (sad/angry people, phones, arguments...).
# Edit these anytime to tune the footage that gets pulled per category.
CATEGORY_SEARCH_QUERIES: Dict[str, str] = {
    "Wife Cheating on Husband": "woman texting secretly upset",
    "Husband Cheating on Wife": "man hiding phone guilty",
    "Boyfriend Cheating": "couple arguing breakup",
    "Girlfriend Cheating": "sad man alone with phone",
    "Cheating with Best Friend": "friends whispering secret",
    "Cheating with Siblings Partner": "family tension argument",
    "Online Dating App Cheating": "woman using phone dating app",
    "Long Distance Relationship Cheating": "video call sad woman",
    "Cheating Before Wedding": "bride crying wedding stress",
    "Cheating During Pregnancy": "pregnant woman sad alone",
    "Cheating with Ex": "couple meeting tension",
    "Workplace Cheating": "office colleagues close conversation",
    "Cheating Caught on Camera or Chat": "man shocked looking at phone",
    "Revenge Cheating": "woman angry crying alone",
    "Cheating Confession Stories": "man talking sad confession",
}


def get_search_query(category: str) -> str:
    """Return the Pexels search query for a category, falling back to the
    category name itself if no mapping is defined."""
    return CATEGORY_SEARCH_QUERIES.get(category, category)


PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PEXELS_PER_PAGE = 15
PEXELS_MAX_PAGES = 20
# Lower resolution = much smaller files = much faster downloads.
# Set back to 1920x1080 if you need full HD for editing.
PREFERRED_WIDTH = 1280
PREFERRED_HEIGHT = 720

# Hard cap: files above this resolution (e.g. 4K/2K) are never downloaded,
# no matter what. Keep this at or below 1080p to guarantee no 4K files.
MAX_ALLOWED_WIDTH = 1920
MAX_ALLOWED_HEIGHT = 1080

MIN_SECONDS_BETWEEN_REQUESTS = 0.35
# More parallel downloads = faster overall throughput (raise further if
# your internet connection can handle it, e.g. 8-10).
MAX_CONCURRENT_DOWNLOADS = 8
MAX_RETRIES_PER_VIDEO = 3
RETRY_BACKOFF_SECONDS = 2.0
# Bigger chunk size = fewer read/write cycles = faster on fast connections.
CHUNK_SIZE_BYTES = 1024 * 1024
MIN_VALID_FILE_SIZE_BYTES = 20_000
# Only emit a GUI progress update every N chunks instead of every chunk,
# to avoid flooding the UI thread with signals (this was slowing things down).
PROGRESS_EMIT_EVERY_N_CHUNKS = 4

ROOT_FOLDER_NAME = "Assets"
FILENAME_DIGITS = 3
LOG_FILE_NAME = "download_log.txt"
STATE_FILE_NAME = "download_state.json"


# ============================================================================
# UTILS
# ============================================================================

def sanitize_folder_name(name: str) -> str:
    illegal = r'<>:"/\|?*'
    return "".join(c for c in name if c not in illegal).strip()


def make_filename(index: int, extension: str = "mp4") -> str:
    return f"{str(index).zfill(FILENAME_DIGITS)}.{extension}"


def format_bytes(num_bytes: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < step:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


def format_speed(bytes_per_second: float) -> str:
    return f"{format_bytes(bytes_per_second)}/s"


def format_eta(seconds: float) -> str:
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "--:--"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


_FILENAME_RE = re.compile(r"^(\d+)\.mp4$", re.IGNORECASE)


def parse_index_from_filename(filename: str) -> int:
    match = _FILENAME_RE.match(filename)
    return int(match.group(1)) if match else -1


# ============================================================================
# LOGGER
# ============================================================================

class AppLogger:
    """Writes to a log file and notifies in-memory listeners (for the GUI panel)."""

    def __init__(self, destination_folder: str):
        self._lock = threading.Lock()
        self._listeners: List[Callable[[str], None]] = []

        os.makedirs(destination_folder, exist_ok=True)
        log_path = os.path.join(destination_folder, LOG_FILE_NAME)

        self._logger = logging.getLogger(f"pexels_downloader_{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._logger.handlers.clear()

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        self._logger.addHandler(file_handler)

        self.log_path = log_path

    def add_listener(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def _notify(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self._lock:
            for cb in self._listeners:
                try:
                    cb(line)
                except Exception:
                    pass

    def info(self, message: str) -> None:
        self._logger.info(message)
        self._notify(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)
        self._notify(f"WARNING: {message}")

    def error(self, message: str) -> None:
        self._logger.error(message)
        self._notify(f"ERROR: {message}")

    def downloaded(self, category: str, filename: str, video_id: int) -> None:
        self.info(f"Downloaded [{category}] {filename} (Pexels ID {video_id})")

    def duplicate_skipped(self, category: str, video_id: int) -> None:
        self.info(f"Skipped duplicate [{category}] Pexels ID {video_id}")

    def failed(self, category: str, video_id: Optional[int], reason: str) -> None:
        vid_str = f"ID {video_id}" if video_id is not None else "unknown ID"
        self.error(f"Failed download [{category}] {vid_str}: {reason}")

    def category_skipped(self, category: str, have: int, requested: int) -> None:
        self.info(f"Category '{category}' already has {have}/{requested} videos. Skipped.")

    def category_resumed(self, category: str, have: int, requested: int) -> None:
        self.info(f"Resuming category '{category}': {have}/{requested} present, downloading {requested - have} more.")

    def api_error(self, message: str) -> None:
        self.error(f"Pexels API error: {message}")

    def rate_limited(self, wait_seconds: float) -> None:
        self.warning(f"Rate limited by Pexels API. Waiting {wait_seconds:.1f}s before retrying.")


# ============================================================================
# API CLIENT
# ============================================================================

@dataclass
class VideoFile:
    url: str
    width: int
    height: int
    quality: str
    file_type: str


@dataclass
class PexelsVideo:
    video_id: int
    width: int
    height: int
    best_file: VideoFile


class PexelsApiError(Exception):
    pass


class RateLimitError(Exception):
    def __init__(self, retry_after: Optional[float] = None):
        super().__init__("Rate limited by Pexels API")
        self.retry_after = retry_after


class PexelsClient:
    def __init__(self, api_key: str, logger: AppLogger):
        self.api_key = api_key
        self.logger = logger
        self._session = requests.Session()
        self._session.headers.update({"Authorization": api_key})
        self._last_request_time = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)

    def search_page(self, query: str, page: int, per_page: int = PEXELS_PER_PAGE) -> Dict[str, Any]:
        self._throttle()
        params = {"query": query, "per_page": per_page, "page": page, "orientation": "landscape"}
        try:
            response = self._session.get(PEXELS_SEARCH_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            raise PexelsApiError(f"Network error contacting Pexels: {exc}") from exc
        finally:
            self._last_request_time = time.time()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(float(retry_after) if retry_after else None)
        if response.status_code == 401:
            raise PexelsApiError("Invalid Pexels API key (HTTP 401).")
        if response.status_code != 200:
            raise PexelsApiError(f"Unexpected HTTP status {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as exc:
            raise PexelsApiError(f"Could not parse Pexels response as JSON: {exc}") from exc

    def search_page_with_retry(self, query: str, page: int, max_retries: int = 3) -> Dict[str, Any]:
        attempt = 0
        while True:
            try:
                return self.search_page(query, page)
            except RateLimitError as exc:
                attempt += 1
                wait = exc.retry_after if exc.retry_after else 5.0 * attempt
                self.logger.rate_limited(wait)
                if attempt >= max_retries:
                    raise
                time.sleep(wait)

    @staticmethod
    def _select_best_file(video_json: Dict[str, Any]) -> Optional[VideoFile]:
        files = video_json.get("video_files", [])
        if not files:
            return None

        def is_landscape(f: Dict[str, Any]) -> bool:
            return (f.get("width") or 0) >= (f.get("height") or 0)

        def within_max_resolution(f: Dict[str, Any]) -> bool:
            # Hard cap: never pick a file wider or taller than MAX_ALLOWED_WIDTH /
            # MAX_ALLOWED_HEIGHT. This is what keeps 4K files out entirely.
            width = f.get("width") or 0
            height = f.get("height") or 0
            return width <= MAX_ALLOWED_WIDTH and height <= MAX_ALLOWED_HEIGHT

        landscape_files = [f for f in files if is_landscape(f)]
        candidates = landscape_files if landscape_files else files

        # Drop anything above the resolution cap (e.g. 4K/2K files) first.
        capped_candidates = [f for f in candidates if within_max_resolution(f)]
        if not capped_candidates:
            # Nothing under the cap for this video (rare) -> skip it entirely
            # rather than falling back to a huge 4K file.
            return None

        exact = [f for f in capped_candidates if f.get("width") == PREFERRED_WIDTH and f.get("height") == PREFERRED_HEIGHT]
        chosen = exact[0] if exact else max(capped_candidates, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))

        return VideoFile(
            url=chosen.get("link", ""),
            width=chosen.get("width") or 0,
            height=chosen.get("height") or 0,
            quality=chosen.get("quality", "unknown"),
            file_type=chosen.get("file_type", "video/mp4"),
        )

    def search_videos(self, query: str, page: int) -> List[PexelsVideo]:
        data = self.search_page_with_retry(query, page)
        results: List[PexelsVideo] = []
        for video_json in data.get("videos", []):
            best_file = self._select_best_file(video_json)
            if best_file is None or not best_file.url:
                continue
            results.append(PexelsVideo(
                video_id=video_json.get("id"),
                width=video_json.get("width", 0),
                height=video_json.get("height", 0),
                best_file=best_file,
            ))
        return results


# ============================================================================
# FILE MANAGER
# ============================================================================

class FileManager:
    def __init__(self, destination_folder: str):
        self.root_path = os.path.join(destination_folder, ROOT_FOLDER_NAME)
        self.state_path = os.path.join(destination_folder, STATE_FILE_NAME)
        self._lock = threading.Lock()
        self._state: Dict[str, Dict] = {"categories": {}}

        os.makedirs(self.root_path, exist_ok=True)
        self._load_state()

    def category_folder(self, category: str) -> str:
        folder = os.path.join(self.root_path, sanitize_folder_name(category))
        os.makedirs(folder, exist_ok=True)
        return folder

    def _load_state(self) -> None:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._state = {"categories": {}}
        self._state.setdefault("categories", {})

    def _save_state(self) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def _category_state(self, category: str) -> Dict:
        cats = self._state["categories"]
        if category not in cats:
            cats[category] = {"downloaded_ids": [], "next_index": 1}
        return cats[category]

    def reconcile_category(self, category: str) -> None:
        folder = self.category_folder(category)
        with self._lock:
            cat_state = self._category_state(category)
            valid_indices: Set[int] = set()
            for filename in os.listdir(folder):
                path = os.path.join(folder, filename)
                idx = parse_index_from_filename(filename)
                if idx == -1:
                    continue
                if os.path.getsize(path) < MIN_VALID_FILE_SIZE_BYTES:
                    os.remove(path)
                    continue
                valid_indices.add(idx)
            cat_state["next_index"] = max(valid_indices, default=0) + 1
            cat_state["_valid_count"] = len(valid_indices)
            self._save_state()

    def valid_video_count(self, category: str) -> int:
        return self._category_state(category).get("_valid_count", 0)

    def next_index(self, category: str) -> int:
        with self._lock:
            return self._category_state(category).get("next_index", 1)

    def is_duplicate(self, category: str, video_id: int) -> bool:
        with self._lock:
            return video_id in self._category_state(category)["downloaded_ids"]

    def record_download(self, category: str, video_id: int, index: int) -> None:
        with self._lock:
            cat_state = self._category_state(category)
            if video_id not in cat_state["downloaded_ids"]:
                cat_state["downloaded_ids"].append(video_id)
            cat_state["next_index"] = max(cat_state.get("next_index", 1), index + 1)
            cat_state["_valid_count"] = cat_state.get("_valid_count", 0) + 1
            self._save_state()

    def reserve_index(self, category: str) -> int:
        with self._lock:
            cat_state = self._category_state(category)
            idx = cat_state.get("next_index", 1)
            cat_state["next_index"] = idx + 1
            self._save_state()
            return idx


# ============================================================================
# DOWNLOAD CONTROLLER + ENGINE
# ============================================================================

@dataclass
class ProgressSnapshot:
    current_category: str
    current_file: str
    total_downloaded: int
    total_requested: int
    remaining: int
    speed_bytes_per_sec: float
    eta_seconds: float
    finished: bool = False


class DownloadController:
    def __init__(self):
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def reset(self) -> None:
        self._stop_event.clear()
        self._pause_event.clear()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def wait_if_paused(self) -> None:
        while self.is_paused and not self.is_stopped:
            time.sleep(0.2)


class Downloader:
    def __init__(
        self,
        api_key: str,
        destination_folder: str,
        videos_per_category: int,
        categories: List[str],
        progress_callback: Callable[[ProgressSnapshot], None],
        controller: DownloadController,
        log_listener: Optional[Callable[[str], None]] = None,
    ):
        self.logger = AppLogger(destination_folder)
        if log_listener is not None:
            self.logger.add_listener(log_listener)
        self.client = PexelsClient(api_key, self.logger)
        self.file_manager = FileManager(destination_folder)
        self.videos_per_category = videos_per_category
        self.categories = categories
        self.progress_callback = progress_callback
        self.controller = controller

        self._total_downloaded_lock = threading.Lock()
        self._total_downloaded = 0
        self._total_requested = videos_per_category * len(categories)

        self._bytes_lock = threading.Lock()
        self._recent_bytes = 0
        self._speed_window_start = time.time()
        self._current_speed = 0.0

    def run(self) -> None:
        self.logger.info("=== Download job started ===")
        already_done = 0
        for category in self.categories:
            self.file_manager.reconcile_category(category)
            have = self.file_manager.valid_video_count(category)
            already_done += min(have, self.videos_per_category)
        with self._total_downloaded_lock:
            self._total_downloaded = already_done

        for category in self.categories:
            if self.controller.is_stopped:
                break
            self._process_category(category)

        finished_cleanly = not self.controller.is_stopped
        self.logger.info("=== Download job finished ===" if finished_cleanly else "=== Download job stopped by user ===")
        self._emit_progress(current_category="", current_file="", finished=True)

    def _process_category(self, category: str) -> None:
        self.controller.wait_if_paused()
        if self.controller.is_stopped:
            return

        self.file_manager.reconcile_category(category)
        have = self.file_manager.valid_video_count(category)
        requested = self.videos_per_category

        if have >= requested:
            self.logger.category_skipped(category, have, requested)
            return

        needed = requested - have
        self.logger.category_resumed(category, have, requested)

        candidates = self._collect_candidates(category, needed)
        if not candidates:
            self.logger.warning(f"No suitable videos found for category '{category}'.")
            return

        self._download_candidates(category, candidates)

    def _collect_candidates(self, category: str, needed: int) -> List[PexelsVideo]:
        candidates: List[PexelsVideo] = []
        page = 1
        collected = 0
        query = get_search_query(category)

        while collected < needed and page <= PEXELS_MAX_PAGES:
            if self.controller.is_stopped:
                break
            self.controller.wait_if_paused()

            try:
                results = self.client.search_videos(query, page)
            except RateLimitError:
                self.logger.api_error(f"Persistent rate limiting while searching '{category}'.")
                break
            except PexelsApiError as exc:
                self.logger.api_error(str(exc))
                break

            if not results:
                break

            for video in results:
                if self.file_manager.is_duplicate(category, video.video_id):
                    self.logger.duplicate_skipped(category, video.video_id)
                    continue
                if any(c.video_id == video.video_id for c in candidates):
                    continue
                candidates.append(video)
                collected += 1
                if collected >= needed:
                    break

            page += 1

        return candidates

    def _download_candidates(self, category: str, candidates: List[PexelsVideo]) -> None:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
            futures = {executor.submit(self._download_single, category, video): video for video in candidates}
            for future in as_completed(futures):
                if self.controller.is_stopped:
                    break
                video = futures[future]
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    self.logger.failed(category, video.video_id, str(exc))

    def _download_single(self, category: str, video: PexelsVideo) -> bool:
        self.controller.wait_if_paused()
        if self.controller.is_stopped:
            return False

        if self.file_manager.is_duplicate(category, video.video_id):
            self.logger.duplicate_skipped(category, video.video_id)
            return False

        index = self.file_manager.reserve_index(category)
        filename = make_filename(index)
        folder = self.file_manager.category_folder(category)
        dest_path = os.path.join(folder, filename)

        self._emit_progress(current_category=category, current_file=filename)

        last_error: Optional[str] = None
        for attempt in range(1, MAX_RETRIES_PER_VIDEO + 1):
            if self.controller.is_stopped:
                return False
            self.controller.wait_if_paused()
            try:
                self._stream_download(video.best_file.url, dest_path, category, filename)
                if self._validate_file(dest_path):
                    self.file_manager.record_download(category, video.video_id, index)
                    self.logger.downloaded(category, filename, video.video_id)
                    with self._total_downloaded_lock:
                        self._total_downloaded += 1
                    self._emit_progress(current_category=category, current_file=filename)
                    return True
                else:
                    last_error = "Downloaded file failed validation (too small / corrupt)."
                    self._safe_remove(dest_path)
            except requests.RequestException as exc:
                last_error = f"Network error: {exc}"
            except OSError as exc:
                last_error = f"File system error: {exc}"

            if attempt < MAX_RETRIES_PER_VIDEO:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        self._safe_remove(dest_path)
        self.logger.failed(category, video.video_id, last_error or "Unknown error")
        return False

    def _stream_download(self, url: str, dest_path: str, category: str, filename: str) -> None:
        chunk_counter = 0
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE_BYTES):
                    if self.controller.is_stopped:
                        raise requests.RequestException("Download cancelled by user.")
                    if chunk:
                        f.write(chunk)
                        self._record_bytes(len(chunk))
                        chunk_counter += 1
                        if chunk_counter % PROGRESS_EMIT_EVERY_N_CHUNKS == 0:
                            self._emit_progress(current_category=category, current_file=filename)

    @staticmethod
    def _validate_file(path: str) -> bool:
        return os.path.exists(path) and os.path.getsize(path) >= MIN_VALID_FILE_SIZE_BYTES

    @staticmethod
    def _safe_remove(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def _record_bytes(self, num_bytes: int) -> None:
        with self._bytes_lock:
            self._recent_bytes += num_bytes
            elapsed = time.time() - self._speed_window_start
            if elapsed >= 1.0:
                self._current_speed = self._recent_bytes / elapsed
                self._recent_bytes = 0
                self._speed_window_start = time.time()

    def _emit_progress(self, current_category: str, current_file: str, finished: bool = False) -> None:
        with self._total_downloaded_lock:
            total_downloaded = self._total_downloaded
        remaining = max(self._total_requested - total_downloaded, 0)
        with self._bytes_lock:
            speed = self._current_speed
        eta = (remaining / (speed / (1024 * 1024 * 5))) if speed > 0 else float("inf")

        snapshot = ProgressSnapshot(
            current_category=current_category,
            current_file=current_file,
            total_downloaded=total_downloaded,
            total_requested=self._total_requested,
            remaining=remaining,
            speed_bytes_per_sec=speed,
            eta_seconds=eta,
            finished=finished,
        )
        try:
            self.progress_callback(snapshot)
        except Exception:
            pass


# ============================================================================
# GUI WORKER THREAD
# ============================================================================

class DownloadWorker(QThread):
    progress_updated = Signal(object)
    log_message = Signal(str)
    job_finished = Signal()
    fatal_error = Signal(str)

    def __init__(self, api_key, destination_folder, videos_per_category, categories, controller):
        super().__init__()
        self.api_key = api_key
        self.destination_folder = destination_folder
        self.videos_per_category = videos_per_category
        self.categories = categories
        self.controller = controller

    def _on_progress(self, snapshot: ProgressSnapshot) -> None:
        self.progress_updated.emit(snapshot)

    def _on_log(self, message: str) -> None:
        self.log_message.emit(message)

    def run(self) -> None:
        try:
            downloader = Downloader(
                api_key=self.api_key,
                destination_folder=self.destination_folder,
                videos_per_category=self.videos_per_category,
                categories=self.categories,
                progress_callback=self._on_progress,
                controller=self.controller,
                log_listener=self._on_log,
            )
            downloader.run()
        except Exception as exc:  # noqa: BLE001
            self.fatal_error.emit(str(exc))
        finally:
            self.job_finished.emit()


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pexels Video Dataset Downloader — Cheating Stories")
        self.setMinimumSize(760, 640)

        self.controller = DownloadController()
        self.worker: Optional[DownloadWorker] = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(14)
        root_layout.setContentsMargins(18, 18, 18, 18)

        root_layout.addWidget(self._build_input_group())
        root_layout.addWidget(self._build_controls_group())
        root_layout.addWidget(self._build_progress_group())
        root_layout.addWidget(self._build_log_group(), stretch=1)

    def _build_input_group(self) -> QGroupBox:
        box = QGroupBox("Settings")
        layout = QGridLayout(box)
        layout.setColumnStretch(1, 1)

        layout.addWidget(QLabel("Pexels API Key:"), 0, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Paste your Pexels API key here")
        layout.addWidget(self.api_key_input, 0, 1, 1, 2)

        self.show_key_btn = QPushButton("Show")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.setFixedWidth(60)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        layout.addWidget(self.show_key_btn, 0, 3)

        layout.addWidget(QLabel("Destination Folder:"), 1, 0)
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Choose where 'Assets/' will be created")
        layout.addWidget(self.folder_input, 1, 1, 1, 2)

        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(60)
        browse_btn.clicked.connect(self._browse_folder)
        layout.addWidget(browse_btn, 1, 3)

        layout.addWidget(QLabel("Videos per Category:"), 2, 0)
        self.videos_per_category_input = QSpinBox()
        self.videos_per_category_input.setRange(1, 500)
        self.videos_per_category_input.setValue(15)
        layout.addWidget(self.videos_per_category_input, 2, 1)

        total_label = QLabel(f"({len(CATEGORIES)} categories)")
        total_label.setStyleSheet("color: gray;")
        layout.addWidget(total_label, 2, 2)

        return box

    def _build_controls_group(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self.start_btn = QPushButton("Start Download")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self._start_download)

        self.pause_resume_btn = QPushButton("Pause")
        self.pause_resume_btn.setMinimumHeight(36)
        self.pause_resume_btn.setEnabled(False)
        self.pause_resume_btn.clicked.connect(self._toggle_pause)

        self.stop_btn = QPushButton("Stop Download")
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_download)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.pause_resume_btn)
        layout.addWidget(self.stop_btn)
        return row

    def _build_progress_group(self) -> QGroupBox:
        box = QGroupBox("Progress")
        layout = QGridLayout(box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar, 0, 0, 1, 4)

        self.category_label = QLabel("Category: —")
        self.file_label = QLabel("File: —")
        self.downloaded_label = QLabel("Downloaded: 0 / 0")
        self.remaining_label = QLabel("Remaining: 0")
        self.speed_label = QLabel("Speed: —")
        self.eta_label = QLabel("ETA: —")

        layout.addWidget(self.category_label, 1, 0)
        layout.addWidget(self.file_label, 1, 1)
        layout.addWidget(self.downloaded_label, 1, 2)
        layout.addWidget(self.remaining_label, 1, 3)
        layout.addWidget(self.speed_label, 2, 0)
        layout.addWidget(self.eta_label, 2, 1)

        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log / Errors")
        layout = QVBoxLayout(box)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(2000)
        layout.addWidget(self.log_panel)
        return box

    def _toggle_key_visibility(self, checked: bool) -> None:
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_key_btn.setText("Hide" if checked else "Show")

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Destination Folder")
        if folder:
            self.folder_input.setText(folder)

    def _validate_inputs(self) -> bool:
        if not self.api_key_input.text().strip():
            QMessageBox.warning(self, "Missing API Key", "Please enter your Pexels API key.")
            return False
        folder = self.folder_input.text().strip()
        if not folder:
            QMessageBox.warning(self, "Missing Folder", "Please choose a destination folder.")
            return False
        if not os.path.isdir(folder):
            QMessageBox.warning(self, "Invalid Folder", "The chosen destination folder does not exist.")
            return False
        return True

    def _start_download(self) -> None:
        if not self._validate_inputs():
            return

        self.controller.reset()
        self.log_panel.clear()

        self.worker = DownloadWorker(
            api_key=self.api_key_input.text().strip(),
            destination_folder=self.folder_input.text().strip(),
            videos_per_category=self.videos_per_category_input.value(),
            categories=list(CATEGORIES),
            controller=self.controller,
        )
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.log_message.connect(self._append_log)
        self.worker.job_finished.connect(self._on_job_finished)
        self.worker.fatal_error.connect(self._on_fatal_error)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.pause_resume_btn.setEnabled(True)
        self.pause_resume_btn.setText("Pause")
        self.stop_btn.setEnabled(True)
        self._set_inputs_enabled(False)

    def _toggle_pause(self) -> None:
        if self.controller.is_paused:
            self.controller.resume()
            self.pause_resume_btn.setText("Pause")
            self._append_log("Download resumed by user.")
        else:
            self.controller.pause()
            self.pause_resume_btn.setText("Resume")
            self._append_log("Download paused by user.")

    def _stop_download(self) -> None:
        self.controller.stop()
        self.controller.resume()
        self._append_log("Stop requested by user. Finishing current file(s)...")
        self.stop_btn.setEnabled(False)
        self.pause_resume_btn.setEnabled(False)

    def _on_job_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.pause_resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._set_inputs_enabled(True)
        self._append_log("Job finished.")

    def _on_fatal_error(self, message: str) -> None:
        self._append_log(f"FATAL ERROR: {message}")
        QMessageBox.critical(self, "Download Error", message)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.api_key_input.setEnabled(enabled)
        self.folder_input.setEnabled(enabled)
        self.videos_per_category_input.setEnabled(enabled)

    def _on_progress(self, snapshot: ProgressSnapshot) -> None:
        if snapshot.total_requested > 0:
            percent = int((snapshot.total_downloaded / snapshot.total_requested) * 100)
            self.progress_bar.setValue(min(percent, 100))

        if snapshot.current_category:
            self.category_label.setText(f"Category: {snapshot.current_category}")
        if snapshot.current_file:
            self.file_label.setText(f"File: {snapshot.current_file}")

        self.downloaded_label.setText(f"Downloaded: {snapshot.total_downloaded} / {snapshot.total_requested}")
        self.remaining_label.setText(f"Remaining: {snapshot.remaining}")
        self.speed_label.setText(f"Speed: {format_speed(snapshot.speed_bytes_per_sec)}")
        self.eta_label.setText(f"ETA: {format_eta(snapshot.eta_seconds)}")

        if snapshot.finished:
            self.category_label.setText("Category: —")
            self.file_label.setText("File: Done")

    def _append_log(self, message: str) -> None:
        self.log_panel.appendPlainText(message)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()