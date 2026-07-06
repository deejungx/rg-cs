import json
from pathlib import Path


class SampleDataService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.data_dir = repo_root / "data"
        self.manifest_path = self.data_dir / "samples.json"

    def list_samples(self) -> list[dict[str, object]]:
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        samples = payload.get("samples", [])
        if not isinstance(samples, list):
            raise ValueError("Sample manifest must contain a samples list.")
        return samples

    def get_sample(self, sample_id: str) -> dict[str, object]:
        for sample in self.list_samples():
            if sample.get("id") == sample_id:
                return sample
        raise FileNotFoundError(f"Unknown sample id: {sample_id}")

    def get_resume_path(self, sample_id: str) -> Path:
        sample = self.get_sample(sample_id)
        relative_path = sample.get("resume_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"Sample {sample_id} does not define a resume_path.")
        path = (self.repo_root / relative_path).resolve()
        data_root = self.data_dir.resolve()
        if data_root not in path.parents:
            raise ValueError("Sample path escapes the data directory.")
        return path


sample_data_service = SampleDataService(Path(__file__).resolve().parents[4])
