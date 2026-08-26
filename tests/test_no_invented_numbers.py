"""Phase 3, work item 3.6: sweep for the rest, and keep it swept.

`governance.py` used to type dollar and percentage figures directly into the
prose it renders -- reserved-matter day-counts, the valuation band, the
buy-sell split -- each one an invented figure with no more provenance than
the ordinary-course threshold Phase 3 already fixed. The sweep pulled every
one of those into a named, documented module constant (or a DerivedNumber,
for the two figures that go through the confirm-or-replace flow).

This file is the ratchet, not the sweep: it enforces that nothing new gets
typed directly into governance.py's rendered text ever again. The scanner
looks for a digit character inside a string or f-string literal, deliberately
excluding docstrings (documentation, not output) and f-string format specs
(formatting directives like ",.0f", not content) -- both of which legitimately
contain digits without being an invented business figure.

Two things are tested, matching the acceptance criteria exactly:

* the real governance.py module has zero such literals today (the sweep is
  complete);
* the scanner itself actually flags a new one when a synthetic sample
  contains it (the mechanism is not vacuous -- a test that only ever passed
  because there was nothing to find would not be a ratchet).
"""

import ast
import re
from pathlib import Path

GOVERNANCE_PATH = Path(__file__).parents[1] / "src" / "tessera_os" / "governance.py"

_DIGIT = re.compile(r"\d")


def find_bare_numeric_literals(source: str) -> list[tuple[int, str]]:
    """Every apparent invented number reaching rendered text, as (line, text).

    A "bare numeric literal reaching rendered text" is either:

    * a digit typed directly into a plain or f-string literal's static text
      (e.g. ``"twelve (12) months"``), or
    * a bare int/float constant interpolated directly into an f-string
      (e.g. ``f"{25}%"``) rather than a named constant or attribute.

    Docstrings and f-string format specs are excluded: neither is rendered
    business content, and both legitimately contain digits (a docstring
    explaining a historical incident, a format spec like ",.0f").
    """
    tree = ast.parse(source)

    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstring_ids.add(id(first.value))

    format_spec_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            for sub in ast.walk(node.format_spec):
                format_spec_ids.add(id(sub))

    bare_interpolation_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Constant):
            value = node.value.value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                bare_interpolation_ids.add(id(node.value))

    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        node_id = id(node)
        if node_id in docstring_ids or node_id in format_spec_ids:
            continue
        if isinstance(node.value, str) and _DIGIT.search(node.value):
            violations.append((node.lineno, node.value))
        elif node_id in bare_interpolation_ids:
            violations.append((node.lineno, repr(node.value)))
    return violations


# --- the sweep is complete today ------------------------------------------------------------

def test_governance_module_has_no_bare_numeric_literals_in_rendered_text():
    source = GOVERNANCE_PATH.read_text()
    violations = find_bare_numeric_literals(source)
    assert violations == [], (
        "governance.py contains numbers typed directly into rendered text; each one must "
        "become a named, documented module constant or a DerivedNumber:\n"
        + "\n".join(f"  line {line}: {text!r}" for line, text in violations))


# --- the ratchet actually catches a new one (this is the point) ------------------------------

def test_the_scanner_catches_a_digit_typed_directly_into_a_string_literal():
    source = 'TEXT = "wait ten (10) business days before serving a notice"\n'
    violations = find_bare_numeric_literals(source)
    assert violations == [(1, "wait ten (10) business days before serving a notice")]


def test_the_scanner_catches_a_bare_number_interpolated_into_an_fstring():
    source = 'def build(x):\n    return f"a shotgun at {25}% of the interest"\n'
    violations = find_bare_numeric_literals(source)
    assert violations == [(2, "25")]


def test_the_scanner_does_not_flag_a_named_constant_used_in_an_fstring():
    """The escape hatch this whole ratchet exists to require: name the number
    once, then reference it -- and the reference itself is not a violation."""
    source = (
        "_SHOTGUN_UNIT_PERCENT = 1\n"
        'def build():\n'
        '    return f"a shotgun at {_SHOTGUN_UNIT_PERCENT}% of the interest"\n'
    )
    assert find_bare_numeric_literals(source) == []


def test_the_scanner_ignores_digits_inside_a_docstring():
    source = (
        "def historical_note():\n"
        '    """The memo once said $60,000 while the document said $25,000."""\n'
        "    return None\n"
    )
    assert find_bare_numeric_literals(source) == []


def test_the_scanner_ignores_digits_inside_a_format_spec():
    source = (
        "def render(value):\n"
        '    return f"${value:,.0f} initially"\n'
    )
    assert find_bare_numeric_literals(source) == []


def test_the_scanner_flags_a_module_level_string_with_no_fstring_involved():
    """A plain (non-f) string is exactly how most of governance.py's prose is
    written, so the ratchet must catch a bare number there too, not just in
    f-strings."""
    source = '_MATTER = "any contract running beyond twelve (12) months"\n'
    violations = find_bare_numeric_literals(source)
    assert violations == [(1, "any contract running beyond twelve (12) months")]
