"""Generate a self-contained offline human review sheet from authoring-v1 bytes."""
import argparse
import html
import json
from pathlib import Path
import sys

from ..workload import encode, sha
from .authoring import MAX_BYTES
from .authoring_lint import add_options, lint_authoring
from .state_records import IntakeError, read_bounded
from ._review_support import CHECKS, document

VERSION = "review-sheet-v1"

STYLE = """
:root {color-scheme: light dark; --bg:#f4f6f8; --panel:#fff; --fg:#192733;
 --muted:#495d6b; --border:#bbc7d0; --accent:#145b7b; --cue:#fff5d9;}
@media (prefers-color-scheme: dark) {
 :root {--bg:#111b23; --panel:#1b2934; --fg:#e8eff4; --muted:#bacad5;
 --border:#536777; --accent:#9edbff; --cue:#3a321f;}}
* {box-sizing:border-box;} body {margin:0; background:var(--bg); color:var(--fg);
 font:16px/1.55 system-ui,sans-serif;} main {max-width:1200px; margin:auto; padding:28px 20px 70px;}
h1,h2,h3,h4 {line-height:1.25;} h1 {font-size:2rem;} h2 {font-size:1.5rem;}
section.task, .review-controls {background:var(--panel); border:1px solid var(--border);
 border-radius:10px; padding:24px; margin:24px 0;} a {color:var(--accent);}
pre,code {font-family:ui-monospace,Consolas,monospace;} pre {white-space:pre-wrap;
 overflow-wrap:anywhere; font-size:.9rem; margin:8px 0;}
.message,.probe,.correction {padding:14px; margin:12px 0; border:1px solid var(--border);
 border-radius:6px;} .probe {border-left:4px solid var(--accent);}
.finding {background:var(--cue); padding:10px 14px; margin:8px 0; border-radius:4px;}
.muted,.filler {color:var(--muted);} .filler {padding:8px 14px; font-style:italic;}
.table-scroll {overflow-x:auto;} table {border-collapse:collapse; width:100%; font-size:.9rem;}
th,td {border:1px solid var(--border); padding:10px; text-align:left; vertical-align:top; min-width:110px;}
th {background:var(--bg);} details {margin:14px 0;} summary {cursor:pointer; font-weight:600;}
label {display:block; margin:10px 0;} input[type=checkbox] {width:19px;height:19px; vertical-align:middle; margin-right:8px;}
input[type=text],textarea {display:block; width:100%; padding:10px; background:var(--bg);
 color:var(--fg); border:1px solid var(--border); border-radius:4px; font:inherit;}
textarea {min-height:100px; resize:vertical;} button {font:inherit; font-weight:600; cursor:pointer;
 padding:10px 18px; background:var(--accent); color:var(--bg); border:0; border-radius:5px;}
.hash {overflow-wrap:anywhere;} :focus-visible {outline:3px solid var(--accent); outline-offset:3px;}
@media (max-width:600px) {main {padding:14px 10px;} section.task,.review-controls {padding:14px;}}
@media print {body {background:white;color:black;} .review-controls button {display:none;} details {break-inside:avoid;}}
"""

SCRIPT = r"""
'use strict';
const meta = JSON.parse(document.getElementById('review-data').textContent);
const sections = Array.from(document.querySelectorAll('section[data-task-id]'));
const status = document.getElementById('review-status');
let storageFailed = false;
function storageKey(taskId) {
  return 'review-input-v1:' + meta.source_sha256 + ':task:' + encodeURIComponent(taskId);
}
function warnStorage() {
  storageFailed = true;
  status.textContent = 'Browser storage unavailable; current checks still export. Download before closing.';
}
function load(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); }
  catch (_) { warnStorage(); return null; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); }
  catch (_) { warnStorage(); }
}
function taskState(section) {
  const checks = {};
  for (const box of section.querySelectorAll('input[data-check]')) checks[box.dataset.check] = box.checked === true;
  return {task_id: section.dataset.taskId, checks, notes: section.querySelector('textarea[data-notes]').value};
}
for (const section of sections) {
  const saved = load(storageKey(section.dataset.taskId));
  for (const box of section.querySelectorAll('input[data-check]')) {
    box.checked = !!(saved && saved.checks && saved.checks[box.dataset.check] === true);
    box.addEventListener('change', () => save(storageKey(section.dataset.taskId), taskState(section)));
  }
  const notes = section.querySelector('textarea[data-notes]');
  notes.value = saved && typeof saved.notes === 'string' ? saved.notes : '';
  notes.addEventListener('input', () => save(storageKey(section.dataset.taskId), taskState(section)));
}
const infoKey = 'review-input-v1:' + meta.source_sha256 + ':reviewer';
const reviewer = document.getElementById('reviewer');
const reviewDate = document.getElementById('review-date');
const defects = document.getElementById('defects');
const savedInfo = load(infoKey);
if (savedInfo) {
  reviewer.value = typeof savedInfo.reviewer === 'string' ? savedInfo.reviewer : '';
  reviewDate.value = typeof savedInfo.date === 'string' ? savedInfo.date : '';
  defects.value = typeof savedInfo.defects === 'string' ? savedInfo.defects : '';
}
function saveInfo() {save(infoKey, {reviewer:reviewer.value, date:reviewDate.value, defects:defects.value});}
for (const input of [reviewer, reviewDate, defects]) input.addEventListener('input', saveInfo);
document.getElementById('export-review').addEventListener('click', () => {
  if (!reviewer.value.trim() || !reviewDate.value.trim()) {
    status.textContent = 'Enter a reviewer and declared review date before export.'; return;
  }
  const tasks = sections.map(taskState);
  for (const task of tasks) save(storageKey(task.task_id), task);
  saveInfo();
  // Keep every nonblank listed defect, even when all checks are marked true.
  const result = {version:'review-input-v1', source_sha256:meta.source_sha256,
    reviewer:reviewer.value, date:reviewDate.value, tasks,
    defects:defects.value.split(/\r?\n/).filter(line => line.trim().length > 0)};
  const blob = new Blob([JSON.stringify(result, null, 2) + '\n'], {type:'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url;
  link.download = 'review-input-' + meta.source_sha256 + '.json';
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  if (!storageFailed) status.textContent = 'Review input downloaded. Unchecked items and defects remain in the export.';
});
"""


def escaped(value):
    return html.escape(str(value), quote=True)


def pretty(value):
    return "<pre>" + escaped(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)) + "</pre>"


def finding_html(finding):
    return '<div class="finding"><strong>' + escaped(finding["code"]) + "</strong>" + pretty(finding) + "</div>"


def probe_html(probe, findings):
    parts = ['<div class="probe" data-probe-id="' + escaped(probe["id"]) + '"><h4>Probe ' + escaped(probe["id"]) + "</h4>",
        "<p>Position: " + escaped(probe["position"]) + "</p>", "<pre>" + escaped(probe["wording"]) + "</pre>"]
    for title, key in (("Expected answer", "expected"), ("Field kinds", "field_map"), ("Set fields", "set_fields"),
                       ("Requirements", "requirements"), ("Unknown answers", "unknown_answers"),
                       ("Alternative answers", "alternative_answers"), ("Outcome routes", "outcomes")):
        parts.append("<h4>" + title + "</h4>" + pretty(probe[key]))
    parts.extend(finding_html(f) for f in findings if f["probe_id"] == probe["id"])
    return "".join(parts) + "</div>"


def message_html(message, probes, findings):
    result = '<div class="message" data-message-id="' + escaped(message["id"]) + '"><strong>' + escaped(message["id"]) + "</strong>"
    result += "<p>Declared recap: " + str(message["recap"]).lower() + "</p><pre>" + escaped(message["text"]) + "</pre>"
    result += "".join(finding_html(f) for f in findings if f["message_id"] == message["id"])
    result += "</div>"
    result += "".join(probe_html(p, findings) for p in probes if p["position"] == message["id"])
    return result


def history_html(task):
    columns = ("Record / version", "Transition message", "Change / status", "Value", "Sources / authority",
               "Valid time / applicability", "Requirements")
    parts = ['<div class="table-scroll"><table><thead><tr>' + "".join("<th>" + title + "</th>" for title in columns) + "</tr></thead><tbody>"]
    for record in task["state_history"]:
        parts.append('<tr><td colspan="7"><strong>' + escaped(record["id"]) + "</strong>" + pretty({k: v for k, v in record.items() if k != "versions"}) + "</td></tr>")
        if not record["versions"]:
            parts.append('<tr><td colspan="7">No declared versions (human review must check absence against text).</td></tr>')
        for version in record["versions"]:
            cells = [record["id"] + " / " + version["id"], version["message"], version["change"] + " / " + version["status"]]
            parts.append("<tr>" + "".join("<td>" + escaped(c) + "</td>" for c in cells))
            parts.extend("<td>" + pretty(value) + "</td>" for value in (version["value"], version["sources"],
                {"time": version["time"], "applicability": version["applicability"]}, version["requirements"]))
            parts.append("</tr>")
    return "".join(parts) + "</tbody></table></div>"


def render_sheet(raw, **lint_options):
    doc = document(raw)
    report = lint_authoring(raw, **lint_options)
    source_hash = sha(raw)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; script-src &#39;unsafe-inline&#39;; style-src &#39;unsafe-inline&#39;; connect-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
        "<title>Authoring human review sheet</title><style>" + STYLE + "</style></head><body><main>",
        "<h1>Authoring human review</h1><p>Private maintainer review material. Lint is advisory; these checks require human judgment. Software does not verify semantics or independence.</p>",
        '<p class="hash">Source SHA-256: <code>' + source_hash + "</code></p>",
        "<p>Dataset: " + escaped(doc["dataset"]) + " · " + str(len(doc["tasks"])) + " tasks</p>",
        "<p>Checks and notes save locally in this browser, keyed by source hash and task ID. A changed source starts with unchecked items. If browser storage is unavailable, export before closing. This file and browser storage contain private text/keys.</p>",
        '<noscript><p>JavaScript is disabled. Source review is readable; checklist persistence and JSON download require JavaScript.</p></noscript>',
        '<div class="review-controls"><h2>Reviewer declaration</h2>',
        '<label>Reviewer<input type="text" id="reviewer" autocomplete="off"></label>',
        '<label>Declared review date<input type="text" id="review-date" placeholder="YYYY-MM-DD or explicit timestamp" autocomplete="off"></label>',
        '<label>Unresolved defects (one per line; every nonblank line is exported)<textarea id="defects"></textarea></label>',
        '<button id="export-review" type="button">Download review input JSON</button>',
        '<p id="review-status" role="status" aria-live="polite">No review is approved automatically. Export may contain unchecked items or defects; assembly will refuse them.</p></div>']
    for task in doc["tasks"]:
        findings = [f for f in report["findings"] if f["task_id"] == task["id"]]
        key_ids = {task["conversation"][0]["id"]}
        key_ids.update(p["position"] for p in task["probes"])
        key_ids.update(f["message_id"] for f in findings if f["message_id"])
        for record in task["state_history"]:
            for version in record["versions"]:
                key_ids.add(version["message"])
                key_ids.update(s["message"] for s in version["sources"])
        parts.append('<section class="task" data-task-id="' + escaped(task["id"]) + '"><h2>' + escaped(task["id"]) + " · " + escaped(task["family"]) + "</h2>")
        parts.append("<h3>Coverage tags</h3>" + pretty(task["coverage_tags"]) + "<h3>Key messages and probes</h3>")
        filler = 0
        for message in task["conversation"]:
            if message["id"] not in key_ids:
                filler += 1
                continue
            if filler:
                parts.append('<p class="filler">... ' + str(filler) + " filler messages ...</p>")
                filler = 0
            parts.append(message_html(message, task["probes"], findings))
        if filler:
            parts.append('<p class="filler">... ' + str(filler) + " filler messages ...</p>")
        parts.append("<details><summary>Full conversation (all messages and scheduled probes)</summary>")
        parts.extend(message_html(m, task["probes"], []) for m in task["conversation"])
        parts.append("</details><h3>Corrections and retry branches</h3>")
        for correction in task["recoveries"]:
            parts.append('<div class="correction"><h4>' + escaped(correction["id"]) + "</h4><pre>" + escaped(correction["text"]) + "</pre>")
            parts.append("<h4>Failure probes</h4>" + pretty(correction["failure_probes"]) + "<h4>Correction spans / new-content spans</h4>" + pretty({"spans": correction["spans"], "new_spans": correction["new_spans"]}))
            parts.extend(finding_html(f) for f in findings if f["message_id"] == correction["id"])
            parts.extend(probe_html(p, findings) for p in task["probes"] if p["position"] == correction["id"])
            parts.append("</div>")
        if not task["recoveries"]:
            parts.append('<p class="muted">No declared correction branches.</p>')
        parts.append("<h3>State history</h3>" + history_html(task) + "<h3>Author predictions</h3>" + pretty(task["predictions"]))
        parts.append("<details><summary>All task lint findings (" + str(len(findings)) + ")</summary>" + "".join(finding_html(f) for f in findings) + "</details>")
        parts.append("<h3>Human checklist</h3>")
        for key, title in CHECKS.items():
            parts.append('<label><input type="checkbox" data-check="' + key + '">' + escaped(title) + "</label>")
        parts.append('<label>Task review notes<textarea data-notes="" aria-label="Notes for ' + escaped(task["id"]) + '"></textarea></label></section>')
    parts.append("<details><summary>Complete advisory lint report and configuration</summary>" + pretty(report) + "</details>")
    meta = {"version": VERSION, "source_sha256": source_hash, "task_ids": [t["id"] for t in doc["tasks"]], "checks": CHECKS}
    data = encode(meta).decode("utf-8").replace("&", r"\u0026").replace("<", r"\u003c").replace(">", r"\u003e").replace("\u2028", r"\u2028").replace("\u2029", r"\u2029")
    parts.append('<script id="review-data" type="application/json">' + data + '</script><script id="review-script">' + SCRIPT + "</script></main></body></html>")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output", help="new HTML file, created exclusively")
    add_options(parser)
    args = parser.parse_args()
    try:
        raw = read_bounded(args.source, MAX_BYTES)
        sheet = render_sheet(raw, window=args.window, status_phrases=args.status_phrases, question_phrases=args.question_phrases)
        with Path(args.output).open("xb") as stream:
            stream.write(sheet.encode("utf-8"))
        result = {"version": VERSION, "status": "created", "source_sha256": sha(raw), "semantics_verified": False}
    except IntakeError as exc:
        result = {"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}
    except OSError as exc:
        result = {"version": VERSION, "status": "rejected", "code": "output_exists" if isinstance(exc, FileExistsError) else "file_unavailable"}
    sys.stdout.buffer.write(encode(result) + b"\n")
    return 0 if result["status"] == "created" else 2


if __name__ == "__main__":
    raise SystemExit(main())
