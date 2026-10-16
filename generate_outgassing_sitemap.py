#!/usr/bin/env python3
"""
NASA GSFC Spacecraft Materials Outgassing Database (outgassing.nasa.gov / etd.gsfc.nasa.gov)
Harvester, Static HTML Mirror Generator, and Onyx Sitemap Generator for GitHub Pages.

Publishes:
- Master Portal Index: index.html
- Official ASTM E595 User Guide: user-guide.html
- 963 Manufacturer 3-Letter Code Directory (NASA RP-1124 Appendix A): manufacturers.html
- 20 Application Category Paginated Catalog Pages (146 HTML pages covering all 13,582 material test records):
  catalog/{category_slug}-p{XX}.html
- Raw & Structured Data Exports:
  OutgassingData-CSV.csv, outgassing_records.jsonl, manufacturer_codes.json, outgassing_catalog.json
- Flat <urlset> XML Sitemaps & URL Lists:
  outgassing_sitemap.xml, sitemap.xml, outgassing_direct_sitemap.xml, outgassing_urls.txt, outgassing_direct_urls.txt
"""

import argparse
import csv
import html
import io
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_DIR = os.path.join(SCRIPT_DIR, "catalog")
MFR_CODES_FILE = os.path.join(SCRIPT_DIR, "manufacturer_codes.json")

GH_PAGES_BASE = "https://oht8woowi8yait9n.github.io/outgassing"
DIRECT_BASE = "https://outgassing.nasa.gov"
RECORDS_PER_PAGE = 100

CATEGORY_DEFINITIONS = [
    ("adhesives-cements", "Adhesives, Conductive Adhesives & Cements"),
    ("coatings-paints-primers", "Coatings, Conformal Coatings, Paints & Primers"),
    ("thermal-electrical-insulation", "Thermal & Electrical Insulation, Blankets & Shields"),
    ("potting-encapsulants", "Potting Compounds & Encapsulants"),
    ("tapes-pressure-sensitive", "Tapes & Pressure-Sensitive Films"),
    ("molding-compounds-resins", "Molding Compounds, Resins, Epoxies & Silicones"),
    ("laminates-circuit-boards", "Laminates, Circuit Boards & Solder Masks"),
    ("sealants-gaskets-orings", "Sealants, Gaskets, O-Rings & Valves"),
    ("wire-cable-tubing-sleeving", "Wire, Cable, Shrink Tubing & Sleeving"),
    ("films-sheets-antistatic", "Films, Sheets, Foils & Anti-Static Materials"),
    ("foams-honeycombs-cellular", "Foams, Honeycombs & Cellular Materials"),
    ("inks-labels-marking", "Inks, Labels, Decals & Marking Materials"),
    ("lubricants-greases-oils", "Lubricants, Greases, Oils & Fluids"),
    ("dampers-mounts-isolators", "Dampers, Mounts, Pads & Vibration Isolators"),
    ("electronic-components-connectors", "Electronic Components, Connectors, Sensors & Heaters"),
    ("structural-composites-fasteners", "Structural Hardware, Composites & Fasteners"),
    ("fabrics-fibers-textiles", "Fabrics, Fibers, Lacing Cord, Velcro & Textiles"),
    ("optical-windows-glasses", "Optical Materials, Lenses, Mirrors & Windows"),
    ("other-specialty-materials", "Other Specialty Spacecraft Materials"),
    ("unspecified-general", "General / Unspecified Application Materials"),
]
CAT_TITLE_MAP = dict(CATEGORY_DEFINITIONS)


def classify_application(raw_app: str) -> str:
    u = (raw_app or "").strip().upper()
    if not u:
        return "unspecified-general"
    if "LACING" in u:
        return "fabrics-fibers-textiles"
    if "ADHESIVE" in u or "ADH" in u or "CEMENT" in u or "GLUE" in u:
        return "adhesives-cements"
    if "POTTING" in u or "ENCAPSUL" in u:
        return "potting-encapsulants"
    if "TAPE" in u:
        return "tapes-pressure-sensitive"
    if "COAT" in u or "PAINT" in u or "PRIMER" in u or "LACQUER" in u or "VARNISH" in u or "ENAMEL" in u:
        return "coatings-paints-primers"
    if "MOLD" in u or "RESIN" in u or "EPOXY" in u or "PLASTIC" in u or "POLYMER" in u or "SILICONE" in u or "URETHANE" in u:
        return "molding-compounds-resins"
    if "LAMINAT" in u or "CIRCUIT" in u or "PC BOARD" in u or "SOLDER" in u:
        return "laminates-circuit-boards"
    if "FOAM" in u or "SPONGE" in u or "HONEYCOMB" in u:
        return "foams-honeycombs-cellular"
    if "GASKET" in u or "SEAL" in u or "O-RING" in u or "VALVE" in u or "GROUT" in u or "CAULK" in u:
        return "sealants-gaskets-orings"
    if "WIRE" in u or "CABLE" in u or "TUBING" in u or "SLEEV" in u or "SHRINK" in u or "HARNESS" in u:
        return "wire-cable-tubing-sleeving"
    if "INSUL" in u or "BLANKET" in u or "THERM" in u or "SHIELD" in u or "ABLATIVE" in u or "HEAT" in u:
        return "thermal-electrical-insulation"
    if "CONN" in u or "SWITCH" in u or "RELAY" in u or "SENSOR" in u or "MOTOR" in u or "ELECTR" in u or "HEATER" in u or "CAPACITOR" in u or "RESISTOR" in u or "TRANSISTOR" in u or "DIODE" in u:
        return "electronic-components-connectors"
    if "FILM" in u or "SHEET" in u or "FOIL" in u or "MEMBRANE" in u or "BAG" in u:
        return "films-sheets-antistatic"
    if "INK" in u or "MARK" in u or "LABEL" in u or "DECAL" in u or "PEN" in u or "RIBBON" in u:
        return "inks-labels-marking"
    if "LUB" in u or "GREASE" in u or "OIL" in u or "FLUID" in u or "WAX" in u:
        return "lubricants-greases-oils"
    if "DAMP" in u or "MOUNT" in u or "PAD" in u or "BUSHING" in u or "BUMPER" in u or "SHOCK" in u or "CUSHION" in u:
        return "dampers-mounts-isolators"
    if "FABRIC" in u or "CLOTH" in u or "THREAD" in u or "CORD" in u or "WEBBING" in u or "VELCRO" in u or "NET" in u or "FELT" in u or "FIBER" in u or "STRAP" in u:
        return "fabrics-fibers-textiles"
    if "OPTIC" in u or "LENS" in u or "MIRROR" in u or "FILTER" in u or "WINDOW" in u or "GLASS" in u:
        return "optical-windows-glasses"
    if "STRUCT" in u or "TUBE" in u or "ROD" in u or "HOUSING" in u or "BRACKET" in u or "FASTENER" in u or "SCREW" in u or "INSERT" in u or "NUT" in u or "WASHER" in u:
        return "structural-composites-fasteners"
    return "other-specialty-materials"


HTML_STYLE = """
<style>
  :root {
    --bg: #0b1120;
    --card: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --pass-bg: #064e3b;
    --pass-text: #6ee7b7;
    --warn-bg: #78350f;
    --warn-text: #fcd34d;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    margin: 0;
    padding: 32px;
  }
  .container { max-width: 1240px; margin: 0 auto; }
  header {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 24px;
  }
  h1 { margin: 0 0 8px 0; color: var(--accent); font-size: 26px; }
  h2 { color: var(--accent); font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-top: 28px; }
  h3 { color: #bae6fd; font-size: 17px; margin: 16px 0 8px 0; }
  p, li { color: #e2e8f0; }
  .meta { color: var(--muted); font-size: 13px; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-pass { background: var(--pass-bg); color: var(--pass-text); }
  .badge-warn { background: var(--warn-bg); color: var(--warn-text); }
  .badge-info { background: #1e3a8a; color: #93c5fd; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 14px;
  }
  th, td {
    border: 1px solid var(--border);
    padding: 8px 12px;
    text-align: left;
    vertical-align: top;
  }
  th { background: #0f172a; color: var(--accent); font-weight: 600; }
  tr:nth-child(even) { background: rgba(15, 23, 42, 0.45); }
  code { background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #bae6fd; font-family: monospace; }
  .nav-bar { margin-bottom: 16px; font-size: 14px; }
  .nav-bar a { margin-right: 18px; font-weight: 500; }
</style>
"""


def wrap_html(title: str, canonical_url: str, body_html: str, prefix: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="canonical" href="{html.escape(canonical_url)}">
  {HTML_STYLE}
</head>
<body>
  <div class="container">
    <div class="nav-bar">
      <a href="{prefix}index.html">Outgassing Database Home</a>
      <a href="{prefix}user-guide.html">ASTM E595 User Guide</a>
      <a href="{prefix}manufacturers.html">Manufacturer Codes (963)</a>
      <a href="{prefix}OutgassingData-CSV.csv">Download Raw CSV</a>
    </div>
    {body_html}
  </div>
</body>
</html>
"""


def format_cure_schedule(row: list) -> str:
    steps = []
    for idx, (t_i, temp_i, atm_i) in enumerate([(7, 8, 9), (10, 11, 12), (13, 14, 15), (16, 17, 18)], start=1):
        t_val = row[t_i].strip() if len(row) > t_i and row[t_i] else ""
        temp_val = row[temp_i].strip() if len(row) > temp_i and row[temp_i] else ""
        atm_val = row[atm_i].strip() if len(row) > atm_i and row[atm_i] else ""
        if t_val or temp_val or atm_val:
            parts = []
            if t_val:
                parts.append(f"Time: {t_val}")
            if temp_val:
                parts.append(f"Temp: {temp_val} °C")
            if atm_val:
                parts.append(f"Atm: {atm_val}")
            steps.append(f"Step {idx} ({', '.join(parts)})")
    return " → ".join(steps) if steps else "Not specified / As received"


def evaluate_outgassing(tml_str: str, cvcm_str: str) -> tuple:
    try:
        tml = float(tml_str)
    except Exception:
        tml = None
    try:
        cvcm = float(cvcm_str)
    except Exception:
        cvcm = None

    if tml is not None and cvcm is not None:
        if tml <= 1.0 and cvcm <= 0.10:
            return True, "PASS — Meets NASA Standard Low-Outgassing Screening Criteria (TML ≤ 1.0%, CVCM ≤ 0.10%)"
        reasons = []
        if tml > 1.0:
            reasons.append(f"TML {tml:.2f}% > 1.0%")
        if cvcm > 0.10:
            reasons.append(f"CVCM {cvcm:.2f}% > 0.10%")
        return False, f"EXCEEDS STANDARD THRESHOLD ({', '.join(reasons)})"
    return False, "INCOMPLETE METRICS"


def main():
    os.makedirs(CATALOG_DIR, exist_ok=True)
    if not os.path.isfile(MFR_CODES_FILE) and os.path.isfile("/opt/gemini/maptis/manufacturer_codes.json"):
        shutil.copy2("/opt/gemini/maptis/manufacturer_codes.json", MFR_CODES_FILE)

    mfr_codes = {}
    if os.path.isfile(MFR_CODES_FILE):
        with open(MFR_CODES_FILE, "r", encoding="utf-8") as f:
            mfr_codes = json.load(f)
    print(f"[*] Loaded {len(mfr_codes):,} manufacturer codes.")

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    })

    # 1. Fetch User Guide
    guide_url = "https://etd.gsfc.nasa.gov/capabilities/outgassing-database/user-guide/"
    try:
        r = session.get(guide_url, timeout=30)
        raw_guide = r.text if r.status_code == 200 else ""
    except Exception as e:
        print(f"[!] Warning fetching User Guide: {e}")
        raw_guide = ""

    m = re.search(r"<main[^>]*>(.*?)</main>", raw_guide, re.S | re.I)
    guide_inner = m.group(1) if m else raw_guide
    guide_inner = re.sub(r"<script[^>]*>.*?</script>", "", guide_inner, flags=re.S | re.I)
    guide_body = f"""
    <header>
      <h1>NASA GSFC Outgassing Database User Guide (ASTM E595 / NASA RP-1124)</h1>
      <div class="meta">Source: <a href="{guide_url}">{guide_url}</a> | Goddard Space Flight Center (GSFC) Materials Engineering Branch (Code 541)</div>
    </header>
    <div class="card">
      {guide_inner}
    </div>
    """
    with open(os.path.join(SCRIPT_DIR, "user-guide.html"), "w", encoding="utf-8") as f:
        f.write(wrap_html("NASA Outgassing Database User Guide (ASTM E595)", guide_url, guide_body))

    # 2. Fetch Outgassing Dataset (CSV + AJAX fallback)
    csv_url = "https://etd.gsfc.nasa.gov/wp-content/uploads/2025/07/OutgassingData-CSV.csv"
    ajax_url = "https://etd.gsfc.nasa.gov/wp-admin/admin-ajax.php?action=load_nasa_data&items_per_page=20000&nasa_page=1"
    raw_rows = []

    try:
        r_csv = session.get(csv_url, timeout=45)
        if r_csv.status_code == 200 and len(r_csv.content) > 100000:
            with open(os.path.join(SCRIPT_DIR, "OutgassingData-CSV.csv"), "wb") as f:
                f.write(r_csv.content)
            parsed = list(csv.reader(io.StringIO(r_csv.content.decode("utf-8-sig", errors="replace"))))
            if len(parsed) > 1:
                raw_rows = parsed[1:]
                print(f"[+] Loaded {len(raw_rows):,} outgassing test records from OutgassingData-CSV.csv")
    except Exception as e:
        print(f"[!] CSV fetch warning: {e}")

    if not raw_rows:
        print("[*] Fetching outgassing data from admin-ajax.php bulk endpoint...")
        r_ajax = session.get(ajax_url, timeout=60)
        d = r_ajax.json()["data"]
        raw_rows = d["data"]
        print(f"[+] Loaded {len(raw_rows):,} outgassing test records from admin-ajax.php")

    # 3. Process records
    records = []
    by_category = defaultdict(list)
    mfr_stats = defaultdict(lambda: {"total": 0, "passed": 0, "apps": Counter()})

    for idx, row in enumerate(raw_rows, start=1):
        while len(row) < 20:
            row.append("")
        mat_name = row[0].strip()
        data_ref = row[1].strip() or f"ROW-{idx}"
        mfr_code = row[2].strip().upper() or "ZZZ"
        tml_str = row[3].strip()
        cvcm_str = row[4].strip()
        wvr_str = row[5].strip()
        app_raw = row[6].strip()
        year_str = row[19].strip()

        mfr_full = mfr_codes.get(mfr_code, f"Manufacturer Code {mfr_code}")
        cat_slug = classify_application(app_raw)
        cat_title = CAT_TITLE_MAP[cat_slug]
        cure_str = format_cure_schedule(row)
        passed, status_label = evaluate_outgassing(tml_str, cvcm_str)

        rec = {
            "id": data_ref,
            "material": mat_name,
            "data_ref": data_ref,
            "mfr_code": mfr_code,
            "mfr_name": mfr_full,
            "tml_pct": tml_str,
            "cvcm_pct": cvcm_str,
            "wvr_pct": wvr_str,
            "application": app_raw or "UNSPECIFIED",
            "category_slug": cat_slug,
            "category_title": cat_title,
            "cure_schedule": cure_str,
            "year": year_str,
            "meets_nasa_screening": passed,
            "screening_status": status_label,
        }
        records.append(rec)
        by_category[cat_slug].append(rec)
        mfr_stats[mfr_code]["total"] += 1
        if passed:
            mfr_stats[mfr_code]["passed"] += 1
        if app_raw:
            mfr_stats[mfr_code]["apps"][app_raw] += 1

    # 4. Generate Manufacturer Code Directory HTML Page
    mfr_rows_html = []
    all_codes = sorted(set(list(mfr_codes.keys()) + list(mfr_stats.keys())))
    for code in all_codes:
        name = mfr_codes.get(code, "Unlisted / Custom GSFC Manufacturer Code")
        st = mfr_stats.get(code, {"total": 0, "passed": 0, "apps": Counter()})
        top_apps = ", ".join(f"{k} ({v})" for k, v in st["apps"].most_common(3))
        mfr_rows_html.append(
            f"<tr id='mfr-{html.escape(code)}'>"
            f"<td><code>{html.escape(code)}</code></td>"
            f"<td><strong>{html.escape(name)}</strong></td>"
            f"<td>{st['total']:,}</td>"
            f"<td>{st['passed']:,}</td>"
            f"<td>{html.escape(top_apps or '—')}</td>"
            f"</tr>"
        )

    mfr_body = f"""
    <header>
      <h1>NASA Spacecraft Materials Manufacturer Code Directory ({len(all_codes):,} Manufacturers)</h1>
      <div class="meta">Source: NASA Reference Publication 1124 (Appendix A) &amp; GSFC Outgassing Database (<code>outgassing.nasa.gov</code>)</div>
    </header>
    <div class="card">
      <p>This directory resolves the three-letter <strong>MFR Code</strong> identifiers used across the NASA GSFC Outgassing Database and MAPTIS non-metallic material records, paired with total ASTM E595 tests and spaceflight low-outgassing qualification counts (TML ≤ 1.0%, CVCM ≤ 0.10%).</p>
      <table>
        <thead>
          <tr>
            <th>Mfr. Code</th>
            <th>Manufacturer Name &amp; Division / Location</th>
            <th>Total Tests</th>
            <th>Low-Outgassing Qualified</th>
            <th>Primary Applications</th>
          </tr>
        </thead>
        <tbody>
          {''.join(mfr_rows_html)}
        </tbody>
      </table>
    </div>
    """
    with open(os.path.join(SCRIPT_DIR, "manufacturers.html"), "w", encoding="utf-8") as f:
        f.write(wrap_html("NASA Outgassing & MAPTIS Manufacturer Codes Directory", f"{GH_PAGES_BASE}/manufacturers.html", mfr_body))

    # 5. Generate Paginated Category HTML Pages in catalog/
    sitemap_entries = [
        {"rel": "index.html", "direct": "https://outgassing.nasa.gov/", "lastmod": "2025-07-09"},
        {"rel": "user-guide.html", "direct": guide_url, "lastmod": "2025-07-09"},
        {"rel": "manufacturers.html", "direct": f"{guide_url}#manufacturers", "lastmod": "2025-07-09"},
    ]
    category_summary = []

    for cat_slug, cat_title in CATEGORY_DEFINITIONS:
        cat_recs = sorted(by_category.get(cat_slug, []), key=lambda r: (r["material"], r["data_ref"]))
        if not cat_recs:
            continue
        total_cat = len(cat_recs)
        passed_cat = sum(1 for r in cat_recs if r["meets_nasa_screening"])
        num_pages = (total_cat + RECORDS_PER_PAGE - 1) // RECORDS_PER_PAGE
        first_page_rel = f"catalog/{cat_slug}-p01.html"

        category_summary.append({
            "slug": cat_slug,
            "title": cat_title,
            "total_records": total_cat,
            "passed_records": passed_cat,
            "num_pages": num_pages,
            "first_page": first_page_rel,
        })

        for p_idx in range(num_pages):
            chunk = cat_recs[p_idx * RECORDS_PER_PAGE : (p_idx + 1) * RECORDS_PER_PAGE]
            page_num = p_idx + 1
            fname = f"{cat_slug}-p{page_num:02d}.html"
            fpath = os.path.join(CATALOG_DIR, fname)
            rel_path = f"catalog/{fname}"
            page_title = f"NASA Outgassing Database: {cat_title} (Part {page_num} of {num_pages} — Records {p_idx*RECORDS_PER_PAGE+1}–{p_idx*RECORDS_PER_PAGE+len(chunk)} of {total_cat})"

            pager_links = [
                f"<a href='{cat_slug}-p{i:02d}.html'>{'<strong>['+str(i)+']</strong>' if i == page_num else 'Part '+str(i)}</a>"
                for i in range(1, num_pages + 1)
            ]
            pager_html = " | ".join(pager_links)

            table_rows = []
            cards_html = []
            for r in chunk:
                badge_cls = "badge-pass" if r["meets_nasa_screening"] else "badge-warn"
                badge_short = "PASS (≤1.0% TML, ≤0.10% CVCM)" if r["meets_nasa_screening"] else "EXCEEDS SCREENING"
                table_rows.append(
                    f"<tr>"
                    f"<td><a href='#{html.escape(r['data_ref'])}'><code>{html.escape(r['data_ref'])}</code></a></td>"
                    f"<td><strong>{html.escape(r['material'])}</strong></td>"
                    f"<td><a href='../manufacturers.html#mfr-{html.escape(r['mfr_code'])}'>{html.escape(r['mfr_code'])}</a> — {html.escape(r['mfr_name'])}</td>"
                    f"<td>{html.escape(r['application'])}</td>"
                    f"<td>{html.escape(r['tml_pct'] or '—')}%</td>"
                    f"<td>{html.escape(r['cvcm_pct'] or '—')}%</td>"
                    f"<td>{html.escape(r['wvr_pct'] or '—')}%</td>"
                    f"<td><span class='badge {badge_cls}'>{badge_short}</span></td>"
                    f"<td>{html.escape(r['year'] or '—')}</td>"
                    f"</tr>"
                )

                cards_html.append(
                    f"<article class='card' id='{html.escape(r['data_ref'])}'>"
                    f"<h3>[{html.escape(r['data_ref'])}] {html.escape(r['material'])}</h3>"
                    f"<p>"
                    f"<span class='badge {badge_cls}'>{html.escape(r['screening_status'])}</span> "
                    f"<span class='badge badge-info'>Category: {html.escape(r['category_title'])} ({html.escape(r['application'])})</span>"
                    f"</p>"
                    f"<ul>"
                    f"<li><strong>Material Designation / Composition:</strong> {html.escape(r['material'])}</li>"
                    f"<li><strong>GSFC Data Reference ID:</strong> <code>{html.escape(r['data_ref'])}</code> (Test Year: {html.escape(r['year'] or 'N/A')})</li>"
                    f"<li><strong>Manufacturer:</strong> <code>{html.escape(r['mfr_code'])}</code> — {html.escape(r['mfr_name'])}</li>"
                    f"<li><strong>ASTM E595 Outgassing Test Results (24h at 125 °C in Vacuum, Collector at 25 °C):</strong> "
                    f"Total Mass Loss (<strong>TML</strong>) = <code>{html.escape(r['tml_pct'] or 'N/A')}%</code> | "
                    f"Collected Volatile Condensable Material (<strong>CVCM</strong>) = <code>{html.escape(r['cvcm_pct'] or 'N/A')}%</code> | "
                    f"Water Vapor Regained (<strong>WVR</strong>) = <code>{html.escape(r['wvr_pct'] or 'N/A')}%</code></li>"
                    f"<li><strong>Cure Schedule (Pre-Test Conditioning):</strong> {html.escape(r['cure_schedule'])}</li>"
                    f"</ul>"
                    f"</article>"
                )

            body = f"""
            <header>
              <h1>{html.escape(page_title)}</h1>
              <div class="meta">
                Source: <a href="https://outgassing.nasa.gov/">https://outgassing.nasa.gov/</a> (NASA GSFC ETD Code 541 Spacecraft Materials Outgassing Database) |
                Category Total: {total_cat:,} tests ({passed_cat:,} Low-Outgassing Qualified)
              </div>
              <p style="margin-top:10px;"><strong>Category Pages:</strong> {pager_html}</p>
            </header>
            <div class="card">
              <h2>Summary Table — {html.escape(cat_title)} (Part {page_num} of {num_pages})</h2>
              <table>
                <thead>
                  <tr>
                    <th>Data Ref</th>
                    <th>Material Designation</th>
                    <th>Manufacturer</th>
                    <th>Application</th>
                    <th>TML %</th>
                    <th>CVCM %</th>
                    <th>WVR %</th>
                    <th>NASA Screening</th>
                    <th>Year</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(table_rows)}
                </tbody>
              </table>
            </div>
            <h2>Detailed ASTM E595 Spacecraft Material Test Records</h2>
            {''.join(cards_html)}
            """
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(wrap_html(page_title, f"{GH_PAGES_BASE}/{rel_path}", body, prefix="../"))

            sitemap_entries.append({
                "rel": rel_path,
                "direct": f"https://outgassing.nasa.gov/#{cat_slug}-p{page_num:02d}",
                "lastmod": "2025-07-09",
            })

    # 6. Build index.html
    passed_total = sum(1 for r in records if r["meets_nasa_screening"])
    cat_rows = "".join(
        f"<tr>"
        f"<td><a href='{html.escape(c['first_page'])}'><strong>{html.escape(c['title'])}</strong></a></td>"
        f"<td>{c['total_records']:,}</td>"
        f"<td>{c['passed_records']:,} ({(100.0 * c['passed_records'] / max(1, c['total_records'])):.1f}%)</td>"
        f"<td>{c['num_pages']} pages</td>"
        f"</tr>"
        for c in category_summary
    )

    index_body = f"""
    <header>
      <h1>NASA GSFC Spacecraft Materials Outgassing Database (ASTM E595)</h1>
      <div class="meta">
        Official Mirror of <a href="https://outgassing.nasa.gov/">https://outgassing.nasa.gov/</a> &amp;
        <a href="https://etd.gsfc.nasa.gov/capabilities/outgassing-database/">etd.gsfc.nasa.gov/capabilities/outgassing-database/</a> |
        Goddard Space Flight Center (GSFC) Materials Engineering Branch
      </div>
    </header>

    <div class="card">
      <h2>Database Overview &amp; Spaceflight Screening Criteria</h2>
      <p>
        This compilation of outgassing data of materials intended for spacecraft use supersedes <strong>NASA Reference Publication 1124, Revision 3</strong>.
        All materials are tested at NASA Goddard Space Flight Center (GSFC) per <strong>ASTM E595-77/84/90</strong>
        (<em>Total Mass Loss (TML) and Collected Volatile Condensable Materials (CVCM) from Outgassing in a Vacuum Environment</em>: 24 hours at 125 °C at &lt;5×10<sup>-5</sup> torr, with volatile condensables collected at 25 °C).
      </p>
      <ul>
        <li><strong>Total ASTM E595 Material Test Records:</strong> <strong>{len(records):,}</strong> (`GSFC` / `GSC` Data References, 1967–present)</li>
        <li><strong>Spaceflight Low-Outgassing Qualified Materials (TML ≤ 1.0% &amp; CVCM ≤ 0.10%):</strong> <strong>{passed_total:,}</strong> ({100.0 * passed_total / max(1, len(records)):.1f}%)</li>
        <li><strong>Aerospace Manufacturers Indexed:</strong> <a href="manufacturers.html"><strong>{len(all_codes):,} Manufacturer 3-Letter Codes</strong></a> (resolved from NASA RP-1124 Appendix A)</li>
        <li><strong>Documentation &amp; Raw Exports:</strong> <a href="user-guide.html"><strong>Official Outgassing User Guide</strong></a> | <a href="OutgassingData-CSV.csv"><strong>Raw CSV Dataset (1.37 MB)</strong></a> | <a href="outgassing_records.jsonl"><strong>Structured JSONL Dataset</strong></a></li>
      </ul>
    </div>

    <div class="card">
      <h2>Browse Outgassing Records by Spacecraft Application Category ({len(records):,} Records across {len(sitemap_entries) - 3} Catalog Pages)</h2>
      <table>
        <thead>
          <tr>
            <th>Application Category</th>
            <th>Total Tests</th>
            <th>Low-Outgassing Qualified (≤1.0% TML, ≤0.10% CVCM)</th>
            <th>Catalog Pages</th>
          </tr>
        </thead>
        <tbody>{cat_rows}</tbody>
      </table>
    </div>
    """
    with open(os.path.join(SCRIPT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(wrap_html("NASA GSFC Spacecraft Materials Outgassing Database (ASTM E595)", f"{GH_PAGES_BASE}/index.html", index_body))

    # 7. Write Sitemaps, URLs, JSONL, and Catalog JSON
    gh_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    direct_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    gh_urls = []
    direct_urls = []

    for e in sitemap_entries:
        gh_loc = f"{GH_PAGES_BASE}/{e['rel']}"
        dir_loc = e["direct"]
        lastmod = e["lastmod"]
        gh_urls.append(gh_loc)
        direct_urls.append(dir_loc)
        gh_xml.append(f"  <url>\n    <loc>{html.escape(gh_loc)}</loc>\n    <lastmod>{html.escape(lastmod)}</lastmod>\n  </url>")
        direct_xml.append(f"  <url>\n    <loc>{html.escape(dir_loc)}</loc>\n    <lastmod>{html.escape(lastmod)}</lastmod>\n  </url>")

    gh_xml.append("</urlset>\n")
    direct_xml.append("</urlset>\n")

    for fname in ["outgassing_sitemap.xml", "sitemap.xml"]:
        with open(os.path.join(SCRIPT_DIR, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(gh_xml))

    with open(os.path.join(SCRIPT_DIR, "outgassing_direct_sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(direct_xml))

    with open(os.path.join(SCRIPT_DIR, "outgassing_urls.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(gh_urls) + "\n")

    with open(os.path.join(SCRIPT_DIR, "outgassing_direct_urls.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(direct_urls) + "\n")

    with open(os.path.join(SCRIPT_DIR, "outgassing_records.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    catalog_meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "passed_records": passed_total,
        "total_manufacturers": len(all_codes),
        "total_sitemap_urls": len(sitemap_entries),
        "categories": category_summary,
    }
    with open(os.path.join(SCRIPT_DIR, "outgassing_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog_meta, f, indent=2)

    print(f"[+] Successfully generated {len(sitemap_entries)} static HTML pages & sitemaps in {SCRIPT_DIR}")


if __name__ == "__main__":
    main()
