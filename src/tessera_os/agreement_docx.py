"""Render an assembled agreement as a branded Word document.

Markdown is fine for review inside the console. It is not what goes to counsel
or a counterparty. This renders the same assembled draft as a Tessera-branded
``.docx`` -- navy, gold, and cream, Cinzel headings over Calibri body -- with
the draft warning, the counsel checklist, and the open-terms list carried into
the document rather than left behind in the tool.

The renderer emits a JavaScript program for the ``docx`` npm package and runs
it. No network access and no external service is involved.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .clauses import AssembledDraft

# Brand tokens, matching the Tessera site stylesheet and the console.
NAVY = "0B1F3A"
GOLD = "B8963E"
GOLD_DEEP = "96792F"
INK = "1B2430"
MUTED = "5B6472"
LINE = "E2E5EA"

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _runs(text: str) -> list[dict]:
    """Split a markdown line into bold and plain runs for docx-js."""
    runs, cursor = [], 0
    for match in _BOLD.finditer(text):
        if match.start() > cursor:
            runs.append({"text": text[cursor:match.start()], "bold": False})
        runs.append({"text": match.group(1), "bold": True})
        cursor = match.end()
    if cursor < len(text):
        runs.append({"text": text[cursor:], "bold": False})
    return runs or [{"text": "", "bold": False}]


def _blocks(markdown: str) -> list[dict]:
    """Flatten assembled markdown into typed blocks the script can render."""
    blocks: list[dict] = []
    table: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table
        if table:
            blocks.append({"kind": "table", "rows": table})
            table = []

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells):
                continue  # markdown table separator
            table.append(cells)
            continue
        flush_table()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"kind": "title", "text": line[2:]})
        elif line.startswith("## "):
            blocks.append({"kind": "h2", "text": line[3:]})
        elif line == "---":
            blocks.append({"kind": "rule"})
        elif line.startswith("- "):
            blocks.append({"kind": "bullet", "runs": _runs(line[2:])})
        elif line.startswith("> "):
            blocks.append({"kind": "note", "text": _BOLD.sub(r"\1", line[2:])})
        else:
            blocks.append({"kind": "body", "runs": _runs(line)})
    flush_table()
    return blocks


_SCRIPT = r"""
const {Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle,
       Table, TableRow, TableCell, WidthType, ShadingType, Header, Footer, PageNumber,
       convertInchesToTwip} = require("docx");
const fs = require("fs");
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const {NAVY, GOLD, GOLD_DEEP, INK, MUTED, LINE} = spec.brand;
const SERIF = "Georgia", SANS = "Calibri";

const rule = () => new Paragraph({spacing:{before:160, after:160},
  border:{bottom:{color:GOLD, space:1, style:BorderStyle.SINGLE, size:6}}, children:[]});

function runs(list, opts={}) {
  return list.map(r => new TextRun({text:r.text, bold:r.bold, font:SANS,
    size:opts.size||20, color:opts.color||INK}));
}

const children = [];
for (const b of spec.blocks) {
  if (b.kind === "title") {
    children.push(new Paragraph({spacing:{after:60},
      children:[new TextRun({text:b.text, bold:true, font:SERIF, size:34, color:NAVY})]}));
  } else if (b.kind === "h2") {
    children.push(new Paragraph({heading:HeadingLevel.HEADING_2, spacing:{before:300, after:120},
      border:{bottom:{color:GOLD, space:3, style:BorderStyle.SINGLE, size:4}},
      children:[new TextRun({text:b.text, bold:true, font:SERIF, size:24, color:NAVY})]}));
  } else if (b.kind === "rule") {
    children.push(rule());
  } else if (b.kind === "bullet") {
    children.push(new Paragraph({bullet:{level:0}, spacing:{after:80, line:280},
      children:runs(b.runs)}));
  } else if (b.kind === "note") {
    children.push(new Paragraph({spacing:{before:80, after:140}, indent:{left:convertInchesToTwip(0.25)},
      border:{left:{color:GOLD, space:8, style:BorderStyle.SINGLE, size:12}},
      children:[new TextRun({text:b.text, italics:true, font:SANS, size:19, color:GOLD_DEEP})]}));
  } else if (b.kind === "table") {
    const cols = b.rows[0].length;
    const width = 9360, colWidth = Math.floor(width / cols);
    const rowsOut = b.rows.map((cells, i) => new TableRow({
      tableHeader: i === 0,
      children: cells.map(c => new TableCell({
        width:{size:colWidth, type:WidthType.DXA},
        shading: i === 0 ? {type:ShadingType.CLEAR, fill:NAVY} : undefined,
        margins:{top:80, bottom:80, left:120, right:120},
        children:[new Paragraph({children:runs([{text:c.replace(/\*\*/g,""), bold:i===0}],
          {size:19, color: i === 0 ? "FFFFFF" : INK})})]}))}));
    children.push(new Table({width:{size:width, type:WidthType.DXA},
      columnWidths:Array(cols).fill(colWidth), rows:rowsOut}));
    children.push(new Paragraph({spacing:{after:160}, children:[]}));
  } else {
    children.push(new Paragraph({spacing:{after:140, line:290}, children:runs(b.runs)}));
  }
}

const doc = new Document({
  styles:{default:{document:{run:{font:SANS, size:20, color:INK}}}},
  sections:[{
    properties:{page:{size:{width:12240, height:15840},
      margin:{top:1080, bottom:1080, left:1080, right:1080}}},
    headers:{default:new Header({children:[new Paragraph({
      border:{bottom:{color:GOLD, space:6, style:BorderStyle.SINGLE, size:6}},
      children:[new TextRun({text:"TESSERA GROUP", bold:true, font:SERIF, size:16, color:NAVY}),
                new TextRun({text:"   |   Draft — for counsel review", font:SANS, size:16,
                             color:MUTED, italics:true})]})]})},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,
      children:[new TextRun({text:spec.footer + "   |   Page ", size:16, color:MUTED}),
                new TextRun({children:[PageNumber.CURRENT], size:16, color:MUTED}),
                new TextRun({text:" of ", size:16, color:MUTED}),
                new TextRun({children:[PageNumber.TOTAL_PAGES], size:16, color:MUTED})]})]})},
    children,
  }],
});
Packer.toBuffer(doc).then(b => {fs.writeFileSync(spec.output, b); console.log("ok");});
"""


class DocxRenderError(RuntimeError):
    """Raised when the Word renderer is unavailable or fails."""


def render_agreement_docx(draft: AssembledDraft, output: Path | str, *,
                          markdown: str | None = None) -> Path:
    """Write the assembled agreement to ``output`` as a branded .docx.

    Pass ``markdown`` from :meth:`ClauseLibrary.fill` to render the version with
    every commercial term supplied; otherwise the unfilled draft is rendered and
    its open terms are listed at the end.
    """
    if shutil.which("node") is None:
        raise DocxRenderError("Node.js is required to render Word documents")
    output = Path(output)
    profile = draft.profile
    spec = {
        "blocks": _blocks(markdown if markdown is not None else draft.to_markdown()),
        "output": str(output),
        "footer": f"{profile.agreement_type.replace('_', ' ').title()} — {profile.opportunity}",
        "brand": {"NAVY": NAVY, "GOLD": GOLD, "GOLD_DEEP": GOLD_DEEP,
                  "INK": INK, "MUTED": MUTED, "LINE": LINE},
    }
    with tempfile.TemporaryDirectory() as work:
        script = Path(work) / "render.js"
        payload = Path(work) / "spec.json"
        script.write_text(_SCRIPT)
        payload.write_text(json.dumps(spec))
        result = subprocess.run(
            ["node", str(script), str(payload)],
            capture_output=True, text=True, timeout=120, check=False,
            cwd=Path(__file__).resolve().parents[2])
        if result.returncode != 0:
            raise DocxRenderError(f"Word rendering failed: {result.stderr.strip()[:400]}")
    if not output.is_file():
        raise DocxRenderError("Word rendering produced no file")
    return output
