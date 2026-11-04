import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_gemini_inputs import ROOT, export, render_revision


class FrozenReviewExportTests(unittest.TestCase):
    def test_consolidated_inputs_preserve_every_complete_text_and_packet_manifest(self):
        for revision in ("D1-HLD-R1", "D1-HLD-R2"):
            packet = ROOT / "reviews" / ("packet-" + revision)
            before = {str(p.relative_to(packet)): hashlib.sha256(p.read_bytes()).hexdigest() for p in packet.rglob('*') if p.is_file()}
            consolidated, spans, manifest = render_revision(packet)
            expected = {r['path'] for r in manifest['files'] if Path(r['path']).suffix not in ('.pdf','.docx')} | {'manifest.json'}
            self.assertEqual({s['path'] for s in spans}, expected)
            self.assertEqual(spans[0]['path'], 'review-prompt.txt')
            for span in spans:
                raw = consolidated[span['start_byte']:span['start_byte']+span['bytes']]
                self.assertEqual(raw, (packet/span['path']).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(), span['sha256'])
            after = {str(p.relative_to(packet)): hashlib.sha256(p.read_bytes()).hexdigest() for p in packet.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_r1_has_only_r1_input_paths_no_review_verdicts_or_r2_payloads(self):
        data, spans, _ = render_revision(ROOT/'reviews/packet-D1-HLD-R1')
        paths = [s['path'] for s in spans]
        self.assertFalse(any('codex-original' in p or 'adjudication' in p or 'D1-HLD-R2' in p for p in paths))
        for forbidden in (b'CR-01', b'CR-02', b'CR-03', b'# Original independent Codex architecture review', b'# Independent review adjudication'):
            self.assertNotIn(forbidden, data)
        self.assertNotIn(b'D1-HLD-R2', data)

    def test_exports_copy_exact_three_original_assignments_and_same_common_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            result = export(output)
            self.assertEqual(len(result['original_assignments']), 3)
            self.assertEqual({Path(x['file']).suffix for x in result['original_assignments']}, {'.pdf','.docx'})
            for item in result['original_assignments']:
                data = (output/item['file']).read_bytes()
                self.assertEqual(len(data), item['bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
            prompts=[]
            for snap in result['snapshots']:
                data=(output/snap['file']).read_bytes();span=snap['text_inputs'][0]
                prompts.append(data[span['start_byte']:span['start_byte']+span['bytes']])
                self.assertEqual(hashlib.sha256(data).hexdigest(), snap['sha256'])
            self.assertEqual(prompts[0],prompts[1])
            self.assertEqual(json.loads((output/'export-manifest.json').read_text()), result)
