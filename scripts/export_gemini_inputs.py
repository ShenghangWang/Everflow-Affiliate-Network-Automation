"""Export exact frozen text inputs and unchanged original assignment binaries.

No working-tree implementation, reviewer output, adjudication or later revision
is added to either consolidated input. Original packets are read-only inputs.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reviews" / "manual-upload"
BINARY_SUFFIXES = {".pdf", ".docx"}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def render_revision(packet):
    manifest_bytes = (packet / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    revision = manifest["revision"]
    inputs = []
    for record in manifest["files"]:
        path = packet / record["path"]
        data = path.read_bytes()
        if len(data) != record["bytes"] or sha(data) != record["sha256"]:
            raise ValueError(f"Frozen input mismatch: {revision}/{record['path']}")
        if path.suffix not in BINARY_SUFFIXES:
            data.decode("utf-8")
            inputs.append((record["path"], data))
    # Put the exact common instruction first; retain every other text input,
    # including duplicated bytes under distinct original path labels.
    inputs.sort(key=lambda pair: (pair[0] != "review-prompt.txt", pair[0]))
    inputs.insert(1, ("manifest.json", manifest_bytes))
    header = (f"# {revision} architecture-review snapshot\n\n"
              "This is a consolidated export of the complete frozen text inputs below, "
              "with original packet-relative path labels. It is an architecture-review "
              "snapshot, not current implementation/test evidence. Historical implementation "
              "statuses inside these inputs may differ from the current prototype. "
              "The three original assignment PDF/DOCX files are supplied separately with "
              "unchanged bytes. No later working-tree file or review response is appended.\n\n")
    output = bytearray(header.encode())
    spans = []
    for path, data in inputs:
        longest = max((len(m.group()) for m in re.finditer(rb"`+", data)), default=0)
        fence = b"`" * max(4, longest + 1)
        title = f"## Original input path: `{path}`\n\n".encode()
        title += f"Source bytes: {len(data)}; SHA-256: `{sha(data)}`\n\n".encode()
        output.extend(title + fence + b"text\n")
        start = len(output)
        output.extend(data)
        spans.append({"path": path, "start_byte": start, "bytes": len(data), "sha256": sha(data)})
        output.extend(b"\n" + fence + b"\n\n")
    return bytes(output), spans, manifest


def export(destination=OUTPUT):
    destination.mkdir(parents=True, exist_ok=True)
    result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "snapshots": [], "original_assignments": []}
    for revision in ("D1-HLD-R1", "D1-HLD-R2"):
        packet = ROOT / "reviews" / ("packet-" + revision)
        data, spans, manifest = render_revision(packet)
        name = f"Gemini-{revision}-architecture-input.md"
        (destination / name).write_bytes(data)
        result["snapshots"].append({"revision": revision, "file": name, "sha256": sha(data),
                                    "packet_manifest_sha256": sha((packet / "manifest.json").read_bytes()),
                                    "frozen_at": manifest["frozen_at"], "text_inputs": spans})
    original_dir = destination / "original-assignments"
    original_dir.mkdir(exist_ok=True)
    for record in json.loads((ROOT / "reviews/packet-D1-HLD-R1/manifest.json").read_bytes())["files"]:
        if Path(record["path"]).suffix not in BINARY_SUFFIXES:
            continue
        source = ROOT / "reviews/packet-D1-HLD-R1" / record["path"]
        target = original_dir / source.name
        shutil.copy2(source, target)
        if sha(target.read_bytes()) != record["sha256"]:
            raise ValueError("Original assignment copy changed")
        result["original_assignments"].append({"file": str(target.relative_to(destination)), "sha256": record["sha256"], "bytes": record["bytes"]})
    (destination / "export-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (destination / "UPLOAD-INSTRUCTIONS.md").write_text('''# Manual Gemini architecture review

Upload `Gemini-D1-HLD-R1-architecture-input.md` and all three files in `original-assignments/` first. The exact common review-prompt.txt is the first source block. Keep R2, Codex findings, adjudication and the current implementation evidence out of the first review.

Preserve Gemini's original R1 response. Then supply `Gemini-D1-HLD-R2-architecture-input.md` with the same three originals for the follow-up. These are architecture-review snapshots; their historical implementation statuses differ from current tests. The frozen packet directories and manifests remain unchanged. export-manifest.json records byte spans and hashes proving that every text input is complete and unchanged in the consolidated file; it is a verification sidecar, not an extra review verdict.

No Gemini call or upload was performed by this exporter. Review status remains pending. When returned, retain each response verbatim with the actual exposed model label (otherwise unknown), receipt date, input revision and file hash. Adjudicate findings against evidence and run affected checks for accepted fixes; do not replace originals with summaries or claim agreement proves correctness.
''')
    return result


if __name__ == "__main__":
    result = export()
    for snapshot in result["snapshots"]:
        print(str((OUTPUT / snapshot["file"]).resolve()))
    for original in result["original_assignments"]:
        print(str((OUTPUT / original["file"]).resolve()))
