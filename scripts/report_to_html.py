#!/usr/bin/env python3
"""Render a report Markdown file into a clean, print-optimized (light-theme) HTML doc.

Usage: python3 scripts/report_to_html.py <input.md> <output.html>

Uses python-markdown if available (best fidelity for tables/code); otherwise falls back
to a minimal built-in converter. The HTML is self-contained (embedded CSS), light-themed,
and page-break-aware so "Print → Save as PDF" (or cupsfilter) yields a memo-quality PDF.
"""
import html as _html
import re
import sys

CSS = """
@page { size: letter; margin: 0.85in 0.9in; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; color: #1a2230;
       line-height: 1.55; font-size: 11.5pt; max-width: 7.2in; margin: 0 auto; padding: 0.4in 0; }
h1 { font-size: 22pt; color: #0f1620; border-bottom: 3px solid #2563eb; padding-bottom: 8px; margin: 0 0 6px; }
h2 { font-size: 15pt; color: #0f1620; border-bottom: 1px solid #d5dde8; padding-bottom: 4px;
     margin: 26px 0 10px; page-break-after: avoid; }
h3 { font-size: 12.5pt; color: #22304a; margin: 18px 0 6px; page-break-after: avoid; }
h4 { font-size: 11.5pt; color: #2563eb; margin: 14px 0 4px; page-break-after: avoid; }
p { margin: 0 0 9px; }
strong { color: #0f1620; }
blockquote { margin: 12px 0; padding: 8px 14px; border-left: 4px solid #2563eb;
             background: #f2f6fc; color: #22304a; font-style: italic; }
ul, ol { margin: 8px 0 12px 22px; } li { margin: 3px 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 9.5pt; page-break-inside: avoid; }
th { background: #eef3fb; color: #22304a; text-align: left; font-weight: 600;
     border: 1px solid #cdd8e6; padding: 5px 8px; }
td { border: 1px solid #dde5ef; padding: 5px 8px; }
code { background: #eef1f5; color: #b1004e; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }
pre { background: #f4f6f9; border: 1px solid #e0e5ec; border-radius: 6px; padding: 10px;
      overflow-x: auto; font-size: 9pt; page-break-inside: avoid; }
pre code { background: none; color: #1a2230; }
hr { border: none; border-top: 1px solid #d5dde8; margin: 22px 0; }
"""


def _minimal_md(md: str) -> str:
    """Tiny fallback converter — handles the constructs our reports actually use."""
    lines = md.split("\n")
    out, i = [], 0
    def inline(t):
        t = _html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\s*\|.*\|\s*$", ln) and i + 1 < len(lines) and re.match(r"^\s*\|[-\s|:]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if ln.startswith(">"):
            out.append(f"<blockquote>{inline(ln.lstrip('> ').rstrip())}</blockquote>"); i += 1; continue
        if re.match(r"^\s*[-*]\s+", ln):
            out.append("<ul>")
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i])
                out.append(f"<li>{inline(item)}</li>")
                i += 1
            out.append("</ul>"); continue
        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue
        if ln.strip() == "":
            i += 1; continue
        out.append(f"<p>{inline(ln)}</p>"); i += 1
    return "\n".join(out)


def to_html(md: str) -> str:
    try:
        import markdown  # type: ignore
        body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        body = _minimal_md(md)
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def main():
    if len(sys.argv) != 3:
        print("usage: report_to_html.py <input.md> <output.html>", file=sys.stderr); sys.exit(2)
    md = open(sys.argv[1]).read()
    open(sys.argv[2], "w").write(to_html(md))
    print(f"wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
