"""
src/github_uploader.py
محرك الرفع التلقائي للقطات والبيانات الحية إلى مستودع GitHub
المستودع المستهدف: https://github.com/lrway312-commits/ana
المجلد: اللقطات الحية
"""

import os
import sys
import json
import base64
import urllib.parse
import urllib.request
import threading
import logging
from typing import Optional, List

logger = logging.getLogger("github_uploader")

# تحميل الإعدادات من البيئة أو ملف .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

def load_env_defaults():
    env = {}
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
        except Exception as e:
            logger.warning(f"Error reading .env: {e}")
    return env

_env_defaults = load_env_defaults()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", _env_defaults.get("GITHUB_TOKEN", "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"))
GITHUB_REPO = os.getenv("GITHUB_REPO", _env_defaults.get("GITHUB_REPO", "lrway312-commits/ana"))
GITHUB_FOLDER = os.getenv("GITHUB_FOLDER", _env_defaults.get("GITHUB_FOLDER", "اللقطات الحية"))
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", _env_defaults.get("GITHUB_BRANCH", "main"))

def get_file_sha(repo: str, remote_path: str, token: str) -> Optional[str]:
    """جلب sha للملف في حال كان موجوداً على جيت هوب لإجراء التحديث"""
    try:
        encoded_path = urllib.parse.quote(remote_path)
        url = f"https://api.github.com/repos/{repo}/contents/{encoded_path}?ref={GITHUB_BRANCH}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ZeroZero-Forensic-Engine"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        logger.warning(f"Check SHA HTTP error {e.code} for {remote_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Check SHA error for {remote_path}: {e}")
        return None

def upload_file_to_github(
    local_path: str,
    remote_folder: Optional[str] = None,
    remote_filename: Optional[str] = None,
    commit_message: Optional[str] = None,
    max_retries: int = 3
) -> bool:
    """
    رفع ملف محلي إلى مستودع GitHub
    يدعم النصوص والملفات الثنائية (صور PNG / JSON)
    """
    if not os.path.exists(local_path):
        logger.error(f"Local file does not exist: {local_path}")
        return False

    if not GITHUB_TOKEN:
        logger.error("GitHub token is missing!")
        return False

    folder = remote_folder if remote_folder is not None else GITHUB_FOLDER
    fname = remote_filename if remote_filename else os.path.basename(local_path)
    remote_path = f"{folder}/{fname}" if folder else fname

    try:
        with open(local_path, "rb") as f:
            content_bytes = f.read()
    except Exception as e:
        logger.error(f"Failed to read local file {local_path}: {e}")
        return False

    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    if not commit_message:
        commit_message = f"feat(live): upload {fname}"

    encoded_path = urllib.parse.quote(remote_path)
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"

    for attempt in range(1, max_retries + 1):
        try:
            # التحقق مما إذا كان الملف موجوداً بالفعل لتضمين الـ sha
            sha = get_file_sha(GITHUB_REPO, remote_path, GITHUB_TOKEN)

            payload = {
                "message": commit_message,
                "content": content_b64,
                "branch": GITHUB_BRANCH
            }
            if sha:
                payload["sha"] = sha

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=data_bytes,
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                    "User-Agent": "ZeroZero-Forensic-Engine"
                },
                method="PUT"
            )

            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 201):
                    logger.info(f"✅ Successfully uploaded to GitHub: {remote_path} (Status {resp.status})")
                    return True
                else:
                    logger.warning(f"Unexpected status code {resp.status} for {remote_path}")

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning(f"Attempt {attempt}/{max_retries} failed for {remote_path}: HTTP {e.code} - {err_body}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed for {remote_path}: {e}")

    logger.error(f"❌ Failed to upload {remote_path} to GitHub after {max_retries} attempts.")
    return False

def upload_file_async(
    local_path: str,
    remote_folder: Optional[str] = None,
    remote_filename: Optional[str] = None,
    commit_message: Optional[str] = None
):
    """رفع الملف في مسار خلفي منفصل (Thread) لتجنب تعطيل الجدولة"""
    t = threading.Thread(
        target=upload_file_to_github,
        args=(local_path, remote_folder, remote_filename, commit_message),
        daemon=True
    )
    t.start()
    return t

def upload_charts_dir(charts_dir: str, remote_folder: str = "اللقطات الحية/charts") -> int:
    """رفع جميع صور الشارتات في مجلد محدد"""
    if not os.path.exists(charts_dir):
        logger.warning(f"Charts directory does not exist: {charts_dir}")
        return 0

    uploaded = 0
    for fname in os.listdir(charts_dir):
        if fname.lower().endswith(".png"):
            fpath = os.path.join(charts_dir, fname)
            success = upload_file_to_github(
                local_path=fpath,
                remote_folder=remote_folder,
                remote_filename=fname,
                commit_message=f"feat(chart): update live chart {fname}"
            )
            if success:
                uploaded += 1
    logger.info(f"Uploaded {uploaded} charts to GitHub folder: {remote_folder}")
    return uploaded

def upload_charts_dir_async(charts_dir: str, remote_folder: str = "اللقطات الحية/charts"):
    """رفع الشارتات في الخلفية بدون انتظار"""
    t = threading.Thread(
        target=upload_charts_dir,
        args=(charts_dir, remote_folder),
        daemon=True
    )
    t.start()
    return t
