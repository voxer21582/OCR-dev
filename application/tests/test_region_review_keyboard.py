"""Synthetic DOM-contract tests for keyboard-driven region selection.

This module reads the inline review script without importing the WSGI app or
its local archive/store dependencies. Node's built-in VM runs the script only
against small in-memory DOM doubles; no browser, file, network, or OCR is used.
"""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


APP_SOURCE = (
    Path(__file__).parents[1]
    / "src"
    / "alfa_document_intelligence"
    / "local_intake_app.py"
)

NODE_HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));

function target(initial = {}) {
  const listeners = Object.create(null);
  return {
    ...initial,
    attrs: { ...(initial.attrs || {}) },
    addEventListener(name, callback) { listeners[name] = callback; },
    dispatch(name, event = {}) {
      if (listeners[name]) listeners[name](event);
    },
    setAttribute(name, value) { this.attrs[name] = String(value); },
  };
}

const svg = target({
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
  setPointerCapture() {},
});
const img = { dataset: { previewBase: '/reviews/doc/pages' }, src: '' };
const rect = target({ attrs: { x: '0', y: '0', width: '0', height: '0' } });
const page = target({ value: '1' });
const status = { textContent: 'Trascina sulla pagina oppure inserisci le coordinate normalizzate.' };
const fields = ['x0', 'y0', 'x1', 'y1'].map(() => target({ value: '' }));
const selectors = new Map([
  ['[data-region-overlay]', svg],
  ['[data-region-image]', img],
  ['[data-region-selection]', rect],
  ['[data-region-page]', page],
  ['[data-region-status]', status],
  ...['x0', 'y0', 'x1', 'y1'].map((name, index) => [`[name=region_${name}]`, fields[index]]),
]);
const form = { querySelector: (selector) => selectors.get(selector) };
const document = { querySelectorAll: () => [form] };
vm.runInNewContext(payload.script, { document });

if (payload.case === 'keyboard-preview') {
  ['0.25', '0.25', '0.75', '0.75'].forEach((value, index) => {
    fields[index].value = value;
    fields[index].dispatch('input');
  });
  assert.equal(rect.attrs.x, '0.25');
  assert.equal(rect.attrs.y, '0.25');
  assert.equal(rect.attrs.width, '0.5');
  assert.equal(rect.attrs.height, '0.5');
  assert.match(status.textContent, /Regione selezionata nella pagina 1/);
} else if (payload.case === 'inverted-x' || payload.case === 'inverted-y') {
  const values = payload.case === 'inverted-x'
    ? ['0.75', '0.25', '0.25', '0.75']
    : ['0.25', '0.75', '0.75', '0.25'];
  values.forEach((value, index) => {
    fields[index].value = value;
    fields[index].dispatch('input');
  });
  assert.equal(rect.attrs.width, '0');
  assert.equal(rect.attrs.height, '0');
  assert.match(status.textContent, /Coordinate invertite/);
} else if (payload.case === 'incomplete-and-invalid') {
  fields[0].value = '0.2';
  fields[0].dispatch('input');
  assert.equal(rect.attrs.width, '0');
  assert.match(status.textContent, /Completa tutte e quattro le coordinate/);
  ['-0.1', '0.2', '0.8', '0.8'].forEach((value, index) => {
    fields[index].value = value;
    fields[index].dispatch('input');
  });
  assert.equal(rect.attrs.width, '0');
  assert.match(status.textContent, /Coordinate non valide/);
} else if (payload.case === 'page-change-clears-selection') {
  ['0.2', '0.2', '0.8', '0.8'].forEach((value, index) => {
    fields[index].value = value;
    fields[index].dispatch('input');
  });
  page.value = '2';
  page.dispatch('change');
  assert.deepEqual(fields.map((field) => field.value), ['', '', '', '']);
  assert.equal(rect.attrs.width, '0');
  assert.equal(img.src, '/reviews/doc/pages/2.png');
  assert.match(status.textContent, /Pagina 2/);
} else if (payload.case === 'pointer-still-syncs') {
  svg.dispatch('pointerdown', { button: 0, clientX: 10, clientY: 10, pointerId: 1 });
  svg.dispatch('pointerup', { button: 0, clientX: 40, clientY: 50, pointerId: 1 });
  assert.equal(fields[0].value, '0.100000');
  assert.equal(fields[1].value, '0.100000');
  assert.equal(fields[2].value, '0.400000');
  assert.equal(fields[3].value, '0.500000');
  assert.equal(rect.attrs.x, '0.1');
  assert.equal(rect.attrs.y, '0.1');
  assert.match(status.textContent, /Regione selezionata nella pagina 1/);
} else {
  throw new Error(`Unknown test case: ${payload.case}`);
}
"""


def _string_expression(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string_expression(node.left) + _string_expression(node.right)
    raise AssertionError("region review script must remain a literal string expression")


def _inline_region_script():
    tree = ast.parse(APP_SOURCE.read_text(encoding="utf-8"), filename=str(APP_SOURCE))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_REGION_REVIEW_SCRIPT"
            for target in node.targets
        ):
            return _string_expression(node.value)
    raise AssertionError("_REGION_REVIEW_SCRIPT was not found")


class RegionReviewKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            raise unittest.SkipTest("Node.js is unavailable for the isolated inline-script contract test")
        cls.script = _inline_region_script()

    def _run_case(self, case):
        result = subprocess.run(
            [self.node, "-e", NODE_HARNESS],
            input=json.dumps({"case": case, "script": self.script}),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_keyboard_coordinates_update_overlay_and_live_status(self):
        self._run_case("keyboard-preview")

    def test_inverted_coordinates_are_rejected_instead_of_misleading_preview(self):
        self._run_case("inverted-x")
        self._run_case("inverted-y")

    def test_partial_or_out_of_range_coordinates_clear_the_preview(self):
        self._run_case("incomplete-and-invalid")

    def test_changing_page_clears_old_region_and_announces_new_page(self):
        self._run_case("page-change-clears-selection")

    def test_pointer_selection_still_updates_coordinates_and_status(self):
        self._run_case("pointer-still-syncs")


if __name__ == "__main__":
    unittest.main()
