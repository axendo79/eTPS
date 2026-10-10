"""SYNTHETIC static-sheet and real JavaScript export/state regressions."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_recovery
from review_tools_fixtures import synthetic_review_document, synthetic_two_task_document
from etps_v02.intake import review_sheet
from etps_v02.intake._review_support import CHECKS
from etps_v02.workload import encode, sha


class SheetParser(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ReviewSheetTests(unittest.TestCase):
    def test_key_messages_filler_full_conversation_and_inline_findings(self):
        raw = encode(synthetic_review_document(giveaways=True))
        html = review_sheet.render_sheet(raw)
        self.assertIn(sha(raw), html)
        self.assertIn('data-message-id="SYNTHETIC-m0"', html)
        self.assertIn('data-message-id="SYNTHETIC-m3"', html)
        self.assertIn('data-message-id="SYNTHETIC-m4"', html)
        self.assertIn("... 2 filler messages ...", html)
        self.assertIn("Full conversation", html)
        self.assertIn("answer_restated_before_probe", html)
        self.assertIn("Expected answer", html)
        self.assertIn("Field kinds", html)
        self.assertIn("Requirements", html)
        self.assertIn("State history", html)
        self.assertIn("Author predictions", html)
        self.assertIn("Coverage tags", html)
        self.assertIn("SYNTHETIC-v0", html)
        self.assertIn("SYNTHETIC_KEY", html)
        self.assertEqual(raw, encode(synthetic_review_document(giveaways=True)))

    def test_every_task_has_five_unchecked_checks_and_notes(self):
        html = review_sheet.render_sheet(encode(synthetic_two_task_document()))
        parser = SheetParser(html)
        checks = [a for tag, a in parser.tags if tag == "input" and a.get("type") == "checkbox"]
        self.assertEqual(len(checks), 2 * len(CHECKS))
        self.assertTrue(all("checked" not in a for a in checks))
        self.assertEqual({a["data-check"] for a in checks}, set(CHECKS))
        notes = [a for tag, a in parser.tags if tag == "textarea" and "data-notes" in a]
        self.assertEqual(len(notes), 2)

    def test_untrusted_text_and_ids_never_become_markup_or_script(self):
        doc = synthetic_review_document()
        payload = '</script><script src="https://SYNTHETIC.invalid/x">SYNTHETIC</script><img onerror="SYNTHETIC">'
        doc["tasks"][0]["id"] = payload.replace("https:", "")
        doc["tasks"][0]["conversation"][1]["text"] += payload
        doc["tasks"][0]["predictions"][0]["reason"] = payload
        html = review_sheet.render_sheet(encode(doc))
        parser = SheetParser(html)
        self.assertEqual(len([t for t, _ in parser.tags if t == "script"]), 2)
        self.assertFalse(any("src" in a or "onerror" in a for _, a in parser.tags))
        self.assertIn("&lt;/script&gt;", html)
        self.assertIn(r"\u003c/script\u003e", html)

    def test_corrections_unknowns_outcomes_and_probes_are_all_visible(self):
        doc = synthetic_recovery()
        html = review_sheet.render_sheet(encode(doc))
        for text in ("SYNTHETIC-recovery", "SYNTHETIC-retry", "Failure probes", "Correction spans",
                     "Unknown answers", "Outcome routes", "Alternative answers"):
            self.assertIn(text, html)

    def test_sheet_is_offline_and_light_dark_readable(self):
        html = review_sheet.render_sheet(encode(synthetic_review_document()))
        parser = SheetParser(html)
        self.assertFalse(any(tag in ("link", "iframe", "img") or "src" in attrs for tag, attrs in parser.tags))
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertIn("color-scheme: light dark", html)
        csp = next(a["content"] for tag, a in parser.tags if tag == "meta" and a.get("http-equiv") == "Content-Security-Policy")
        self.assertIn("connect-src 'none'", csp)
        self.assertNotRegex(html, r"\b(fetch|XMLHttpRequest|WebSocket)\s*\(")
        self.assertEqual(html, review_sheet.render_sheet(encode(synthetic_review_document())))

    def test_cli_creates_exclusively_and_invalid_source_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-sheet-") as temp:
            source, output = Path(temp) / "SYNTHETIC.json", Path(temp) / "SYNTHETIC.html"
            source.write_bytes(encode(synthetic_review_document()))
            args = [sys.executable, "-B", "-m", "etps_v02.intake.review_sheet", str(source), str(output)]
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            first = output.read_bytes()
            self.assertEqual(json.loads(result.stdout)["source_sha256"], sha(source.read_bytes()))
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), first)
            source.write_bytes(b'SYNTHETIC invalid')
            output.unlink()
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
            self.assertFalse(output.exists())

    @unittest.skipUnless(shutil.which("node"), "optional Node for executing embedded offline sheet script")
    def test_script_download_export_restoration_hash_isolation_and_storage_failure(self):
        html = review_sheet.render_sheet(encode(synthetic_two_task_document()))
        data = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S)[1]
        script = re.search(r'<script id="review-script">(.*?)</script>', html, re.S)[1]
        # Execute the actual browser script using a tiny DOM/storage/download
        # harness, rather than testing a second implementation of export logic.
        harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const payload = JSON.parse(require('node:fs').readFileSync(process.argv[2], 'utf8'));
const store = new Map();
function open(meta, unavailable=false) {
  const elems = new Map(); let savedBlob; let downloaded=false;
  function element(id) {
    if (!elems.has(id)) elems.set(id, {id, value:'', checked:false, textContent:'', handlers:{},
      addEventListener(type, fn){this.handlers[type]=fn;}, click(){if(this.handlers.click)this.handlers.click();}, remove(){}});
    return elems.get(id);
  }
  const sections = meta.task_ids.map((id, i) => {
    const checks = Object.keys(meta.checks).map((key, j) => Object.assign(element(`c${i}-${j}`), {dataset:{check:key}}));
    const notes = element(`notes${i}`);
    return {dataset:{taskId:id}, querySelectorAll(){return checks;}, querySelector(){return notes;}};
  });
  const context = {console, JSON, Date, encodeURIComponent, Blob: class {constructor(parts){savedBlob=parts.join('');}},
    URL:{createObjectURL(){return 'blob:SYNTHETIC';},revokeObjectURL(){}},
    setTimeout(fn){fn();},
    localStorage:{getItem(k){if(unavailable)throw Error('SYNTHETIC storage off'); return store.get(k)||null;},
      setItem(k,v){if(unavailable)throw Error('SYNTHETIC storage off'); store.set(k,v);}},
    document:{getElementById(id){const e=element(id); if(id==='review-data')e.textContent=JSON.stringify(meta); return e;},
      querySelectorAll(){return sections;}, createElement(){return {click(){downloaded=true;},remove(){}};},
      body:{appendChild(){}}}};
  vm.runInNewContext(payload.script, context);
  return {element, sections, export(){element('export-review').click(); assert.ok(downloaded); return JSON.parse(savedBlob);}};
}
const meta = JSON.parse(payload.data);
const first = open(meta);
first.element('reviewer').value='SYNTHETIC human simulation';
first.element('review-date').value='SYNTHETIC date';
first.element('defects').value='SYNTHETIC defect one\nSYNTHETIC defect two'.replace('\\n','\n');
for (const s of first.sections) { for(const c of s.querySelectorAll()) c.checked=true; s.querySelector().value='SYNTHETIC notes'; }
const result = first.export();
assert.equal(result.version, 'review-input-v1');
assert.equal(result.source_sha256, meta.source_sha256);
assert.equal(result.tasks.length,2);
assert.ok(result.tasks.every(t=>Object.values(t.checks).every(v=>v===true)));
assert.ok(result.tasks.every(t=>t.notes==='SYNTHETIC notes'));
assert.deepEqual(result.defects,['SYNTHETIC defect one','SYNTHETIC defect two']);
const restored=open(meta);
assert.ok(restored.sections.every(s=>s.querySelectorAll().every(c=>c.checked)));
assert.equal(restored.element('defects').value,first.element('defects').value);
const changed=open({...meta,source_sha256:'SYNTHETIC_CHANGED_HASH'});
assert.ok(changed.sections.every(s=>s.querySelectorAll().every(c=>!c.checked)));
assert.ok([...store.keys()].some(k=>k.includes(meta.source_sha256)&&k.includes(encodeURIComponent(meta.task_ids[0]))));
const noStorage=open(meta,true);
noStorage.element('reviewer').value='SYNTHETIC offline reviewer'; noStorage.element('review-date').value='SYNTHETIC date';
assert.equal(noStorage.export().tasks[0].checks.conversation_supports_answers,false);
assert.match(noStorage.element('review-status').textContent,/storage/i);
'''
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-js-") as temp:
            runner, fixture = Path(temp) / "SYNTHETIC.js", Path(temp) / "SYNTHETIC.json"
            runner.write_text(harness, encoding="utf-8")
            fixture.write_text(json.dumps({"script": script, "data": data}), encoding="utf-8")
            result = subprocess.run([shutil.which("node"), str(runner), str(fixture)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
