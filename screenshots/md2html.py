# -*- coding: utf-8 -*-
"""md2html.py —— 极简 Markdown → HTML（标题/表格/列表/代码块/引用/粗体/行内代码），
   用于把 docs/*.md 渲染成文档预览并截图（截图9）。"""
import html
import re
import sys

CSS = """
<style>
  body { margin:0; background:#f4f5f7; font-family:"Noto Sans CJK SC","Droid Sans Fallback",sans-serif; }
  .page { width:1120px; margin:0 auto; background:#fff; padding:44px 56px 56px;
          box-shadow:0 1px 10px rgba(0,0,0,.12); }
  h1 { font-size:32px; margin:0 0 18px; padding-bottom:12px; border-bottom:3px solid #2d6cdf; color:#1a2233; }
  h2 { font-size:22px; margin:30px 0 12px; color:#1a2233; border-left:5px solid #2d6cdf; padding-left:10px; }
  h3 { font-size:18px; margin:22px 0 8px; color:#25314a; }
  p, li { font-size:15px; line-height:1.85; color:#2a3546; }
  table { border-collapse:collapse; width:100%; margin:12px 0 18px; font-size:14px; }
  th, td { border:1px solid #cfd6e0; padding:8px 10px; text-align:left; }
  th { background:#eef3fb; color:#1a2233; font-weight:600; }
  tr:nth-child(even) td { background:#fafbfd; }
  code { background:#eef1f5; padding:1px 5px; border-radius:3px;
         font-family:"DejaVu Sans Mono",monospace; font-size:13px; color:#b3335b; }
  pre { background:#1f2430; color:#e6ebf2; padding:14px 16px; border-radius:6px; overflow:hidden; }
  pre code { background:none; color:#e6ebf2; padding:0; font-size:13px; line-height:1.6; }
  blockquote { margin:14px 0; padding:8px 14px; background:#f2f6fd;
               border-left:4px solid #7aa7e8; color:#33445c; font-size:14px; }
  hr { border:0; border-top:1px dashed #c3ccd9; margin:26px 0 14px; }
  em { color:#5a6b82; font-size:13px; }
</style>
"""


def inline(t):
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
    return t


def convert(md):
    out, i, lines = [], 0, md.splitlines()
    in_code = False
    while i < len(lines):
        ln = lines[i]
        s = ln.rstrip()
        if s.startswith("```"):
            if not in_code:
                out.append("<pre><code>")
                in_code = True
            else:
                out.append("</code></pre>")
                in_code = False
            i += 1
            continue
        if in_code:
            out.append(html.escape(s))
            i += 1
            continue
        if not s.strip():
            i += 1
            continue
        if s.startswith("# "):
            out.append(f"<h1>{inline(s[2:])}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("### "):
            out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(inline(lines[i].lstrip("> ").strip()))
                i += 1
            out.append("<blockquote>" + "<br>".join(buf) + "</blockquote>")
            continue
        elif s.strip() == "---":
            out.append("<hr>")
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row)
                i += 1
            body = rows[0]
            data = [r for r in rows[1:] if not re.fullmatch(r"[:\-\s|]+", "|".join(r))]
            out.append("<table><thead><tr>" +
                       "".join(f"<th>{inline(c)}</th>" for c in body) +
                       "</tr></thead><tbody>")
            for r in data:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            continue
        elif re.match(r"^(\-|\d+\.)\s", s):
            ordered = bool(re.match(r"^\d+\.", s))
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^(\-|\d+\.)\s", lines[i].strip()):
                item = re.sub(r"^(-|\d+\.)\s+", "", lines[i].strip())
                out.append(f"<li>{inline(item)}</li>")
                i += 1
            out.append(f"</{tag}>")
            continue
        else:
            out.append(f"<p>{inline(s)}</p>")
        i += 1
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def build(md_path, html_path):
    md = open(md_path, encoding="utf-8").read()
    html_doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{html.escape(md_path)}</title>{CSS}</head><body>"
                f"<div class='page'>{convert(md)}</div></body></html>")
    open(html_path, "w", encoding="utf-8").write(html_doc)
    return html_path


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2]))