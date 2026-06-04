import threading
import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from downloader import extract_tiktok_id, sanitize_filename, download_video_tikwm
from video_metadata import save_video_metadata, save_batch_csv, generate_youtube_metadata

managers = {}


MIN_WORKERS = 1
MAX_WORKERS = 10
SPEED_WINDOW = 10  # seconds to average speed over
STALL_TIMEOUT = 30  # seconds without progress = stalled


class DownloadManager:
    def __init__(self, task_id, task_dir, urls, on_update):
        self.task_id = task_id
        self.task_dir = Path(task_dir)
        self.urls = urls
        self.on_update = on_update

        self.total = len(urls)
        self.completed = 0
        self.failed = 0
        self.files = []
        self.status = "processing"
        self.message = "Starting..."

        self.workers = MIN_WORKERS
        self.speed_samples = []
        self.last_byte_count = 0
        self.byte_count = 0
        self.start_time = time.time()
        self.last_progress_time = time.time()

        self._metadata = []
        self._lock = threading.Lock()
        self._cancel = False

    def get_state(self):
        elapsed = time.time() - self.start_time
        done = self.completed + self.failed
        speed = self._get_speed()
        eta = ""
        if speed > 0 and done < self.total:
            remaining = self.total - done
            eta_secs = remaining / speed if speed > 0 else 0
            eta = self._format_eta(eta_secs)
        return {
            "id": self.task_id,
            "status": self.status,
            "progress": int(done / self.total * 100) if self.total else 0,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "message": self.message,
            "files": self.files,
            "error": None,
            "workers": self.workers,
            "speed": round(speed, 1),
            "eta": eta,
            "elapsed": round(elapsed),
        }

    def _get_speed(self):
        now = time.time()
        cutoff = now - SPEED_WINDOW
        self.speed_samples = [(t, b) for t, b in self.speed_samples if t > cutoff]
        if len(self.speed_samples) < 2:
            return 0
        dt = self.speed_samples[-1][0] - self.speed_samples[0][0]
        db = self.speed_samples[-1][1] - self.speed_samples[0][1]
        return db / dt if dt > 0 else 0

    def _format_eta(self, secs):
        if secs < 60:
            return f"{int(secs)}s"
        if secs < 3600:
            return f"{int(secs // 60)}m {int(secs % 60)}s"
        return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"

    def _record_bytes(self, n):
        now = time.time()
        self.byte_count += n
        self.speed_samples.append((now, self.byte_count))
        cutoff = now - SPEED_WINDOW
        self.speed_samples = [(t, b) for t, b in self.speed_samples if t > cutoff]

    def _tune_workers(self):
        speed = self._get_speed()
        done = self.completed + self.failed
        remaining = self.total - done
        if remaining <= 1:
            return
        if speed == 0:
            return

        if speed > 3:
            new_w = min(self.workers + 1, MAX_WORKERS)
        elif speed < 0.5:
            new_w = max(self.workers - 1, MIN_WORKERS)
        else:
            new_w = self.workers

        if new_w != self.workers:
            self.workers = new_w
            self.message = f"{done}/{self.total} ({self.completed} OK, {self.failed} failed) | {new_w} workers"

    def _download_one(self, url):
        vid = extract_tiktok_id(url) or "unknown"
        fn = sanitize_filename(vid)
        retries = 0
        backoff = 2
        while True:
            if self._cancel:
                return False, None
            ok, tikwm_data = download_video_tikwm(url, str(self.task_dir), fn)
            if ok:
                meta = None
                try:
                    if tikwm_data:
                        meta = generate_youtube_metadata(tikwm_data)
                        meta["filename"] = fn + ".mp4"
                        save_video_metadata(Path(self.task_dir) / (fn + ".mp4"), tikwm_data)
                except Exception:
                    meta = None
                for ext in [".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv"]:
                    f = Path(self.task_dir) / f"{fn}{ext}"
                    if f.exists():
                        sz = f.stat().st_size
                        with self._lock:
                            self.files.append({
                                "name": f.name,
                                "path": str(f.relative_to(self.task_dir.parent)),
                                "size": sz,
                                "downloaded_at": time.time(),
                            })
                            self._record_bytes(sz)
                            if meta:
                                self._metadata.append(meta)
                        break
                return True, tikwm_data
            retries += 1
            delay = backoff * min(retries, 10)
            with self._lock:
                self.message = f"Retry {retries} for {vid} in {delay}s..."
            time.sleep(delay)

    def run(self):
        managers[self.task_id] = self
        self.task_dir.mkdir(exist_ok=True)
        self.start_time = time.time()
        self.last_progress_time = time.time()

        completed = 0
        failed = 0
        dl_lock = threading.Lock()

        def worker_fn(url):
            nonlocal completed, failed
            ok, _ = self._download_one(url)
            with dl_lock:
                if ok:
                    completed += 1
                else:
                    failed += 1
                self.completed = completed
                self.failed = failed
                done = completed + failed
                self.message = f"{done}/{self.total} ({completed} OK, {failed} failed) | {self.workers} workers"
                self.last_progress_time = time.time()
                self._tune_workers()
                self.on_update(self.get_state())

        self.on_update(self.get_state())

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = {pool.submit(worker_fn, u): u for u in self.urls}
            done_count = 0
            while done_count < self.total and not self._cancel:
                done_futures = [f for f in futs if f.done()]
                for f in done_futures:
                    if f not in futs:
                        continue
                    del futs[f]
                    done_count += 1
                if self._cancel:
                    pool.shutdown(wait=False)
                    break
                if not futs:
                    break
                time.sleep(0.5)

        if self._cancel:
            self.status = "cancelled"
            self.message = "Cancelled"
        else:
            self.status = "completed"
            self.message = f"Done! {completed} successful, {failed} failed"
        try:
            save_batch_csv(self.task_dir, self._metadata)
        except Exception:
            pass
        self.on_update(self.get_state())

    def cancel(self):
        self._cancel = True
