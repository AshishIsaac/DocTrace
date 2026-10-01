"""Optional Google Drive source (service-account auth).

Share the Drive folder with the service account's e-mail address, then set
GDRIVE_FOLDER_ID and GDRIVE_CREDENTIALS in .env.
"""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .extract import SUPPORTED_EXTS
from .store import FileRecord

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER = "application/vnd.google-apps.folder"
SHORTCUT = "application/vnd.google-apps.shortcut"
# Google-native formats have no bytes of their own; export them to something we can parse.
EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
}
FIELDS = "nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime, size, " \
         "webViewLink, shortcutDetails)"


@dataclass
class DriveFile:
    record: FileRecord
    file_id: str
    mime: str
    ext: str


class Drive:
    def __init__(self, credentials_file: Path):
        from google.oauth2 import service_account

        if not credentials_file.exists():
            raise FileNotFoundError(f"Drive credentials not found: {credentials_file}")
        self.creds = service_account.Credentials.from_service_account_file(
            str(credentials_file), scopes=SCOPES
        )
        self._local = threading.local()  # googleapiclient services are not thread-safe

    @property
    def api(self):
        if not hasattr(self._local, "api"):
            from googleapiclient.discovery import build

            self._local.api = build("drive", "v3", credentials=self.creds, cache_discovery=False)
        return self._local.api

    def _children(self, folder_id: str):
        token = None
        while True:
            res = self.api.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields=FIELDS, pageSize=1000, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            yield from res.get("files", [])
            token = res.get("nextPageToken")
            if not token:
                return

    def scan(self, folder_id: str, max_file_mb: float) -> list[DriveFile]:
        out: list[DriveFile] = []
        seen_folders: set[str] = set()
        max_bytes = max_file_mb * 1024 * 1024

        def walk(fid: str, prefix: str) -> None:
            if fid in seen_folders:
                return
            seen_folders.add(fid)
            for f in self._children(fid):
                mime, file_id = f["mimeType"], f["id"]
                if mime == SHORTCUT:
                    details = f.get("shortcutDetails", {})
                    mime, file_id = details.get("targetMimeType", ""), details.get("targetId", "")
                path = f"{prefix}/{f['name']}" if prefix else f["name"]
                if mime == FOLDER:
                    walk(file_id, path)
                    continue
                if mime in EXPORTS:
                    ext = EXPORTS[mime][1]
                else:
                    ext = PurePosixPath(f["name"]).suffix.lower()
                    if ext not in SUPPORTED_EXTS or int(f.get("size", 0)) > max_bytes:
                        continue
                out.append(DriveFile(
                    record=FileRecord(
                        source="gdrive",
                        path=path,
                        version=f.get("md5Checksum") or f.get("modifiedTime", ""),
                        uri=f.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view",
                    ),
                    file_id=file_id, mime=mime, ext=ext,
                ))

        walk(folder_id, "")
        return out

    def download(self, f: DriveFile) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload

        files = self.api.files()
        if f.mime in EXPORTS:
            req = files.export_media(fileId=f.file_id, mimeType=EXPORTS[f.mime][0])
        else:
            req = files.get_media(fileId=f.file_id, supportsAllDrives=True)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
