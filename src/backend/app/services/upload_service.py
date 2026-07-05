from pathlib import Path
import uuid

from fastapi import UploadFile

from app.core.config import settings


class UploadService:
    def __init__(self, uploads_dir: Path) -> None:
        self.uploads_dir = uploads_dir

    async def save_cv(self, file: UploadFile) -> dict[str, str]:
        candidate_id = str(uuid.uuid4())
        destination_dir = self.uploads_dir / "resumes" / candidate_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        filename = file.filename or "original_resume.bin"
        destination = destination_dir / filename
        contents = await file.read()
        destination.write_bytes(contents)
        return {
            "candidate_id": candidate_id,
            "filename": filename,
            "absolute_path": str(destination),
            "path": str(destination.relative_to(self.uploads_dir.parent)),
            "content_type": file.content_type or "",
        }


upload_service = UploadService(settings.uploads_dir)
