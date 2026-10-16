# NASA GSFC Spacecraft Materials Outgassing Database Mirror & Sitemap (`outgassing.nasa.gov`)

Automated static HTML mirror, structured JSONL/CSV dataset, 3-letter manufacturer code dictionary (`963` manufacturers from NASA RP-1124 Appendix A), and flat `<urlset>` XML sitemaps for the **NASA Goddard Space Flight Center (GSFC) Spacecraft Materials Outgassing Database** (`https://outgassing.nasa.gov` / `https://etd.gsfc.nasa.gov/capabilities/outgassing-database/`).

---

## 📊 Dataset Overview

| Metric | Value |
| :--- | :--- |
| **Upstream Authority** | NASA GSFC Engineering and Technology Directorate (ETD), Materials Engineering Branch (Code 541) |
| **Test Standard** | **ASTM E595-77/84/90** (*Total Mass Loss and Collected Volatile Condensable Materials from Outgassing in a Vacuum Environment* — 24h at $125\,^\circ\text{C}$ in $<5\times 10^{-5}\text{ torr}$ vacuum, collector at $25\,^\circ\text{C}$) / **NASA SP-R-0022A** / **NASA RP-1124** |
| **Total Material Test Records** | **13,582** |
| **Low-Outgassing Spaceflight Qualified** ($\text{TML} \le 1.0\%$ and $\text{CVCM} \le 0.10\%$) | **8,504** ($62.6\%$) |
| **Resolved 3-Letter Manufacturer Codes** | **963** (extracted from NASA Reference Publication 1124 Appendix A) |
| **Application Categories** | **20** spacecraft engineering material categories (**146** paginated HTML catalog pages + index + User Guide + Manufacturer Directory = **149** HTML pages) |

---

## 🔗 Live GitHub Pages & Sitemap Endpoints

- **Portal Landing Page**: [`https://oht8woowi8yait9n.github.io/outgassing/`](https://oht8woowi8yait9n.github.io/outgassing/)
- **Primary Sitemap (`149` Static HTML Pages)**: [`https://oht8woowi8yait9n.github.io/outgassing/outgassing_sitemap.xml`](https://oht8woowi8yait9n.github.io/outgassing/outgassing_sitemap.xml)
- **Standard Sitemap Alias**: [`https://oht8woowi8yait9n.github.io/outgassing/sitemap.xml`](https://oht8woowi8yait9n.github.io/outgassing/sitemap.xml)
- **Official ASTM E595 User Guide**: [`https://oht8woowi8yait9n.github.io/outgassing/user-guide.html`](https://oht8woowi8yait9n.github.io/outgassing/user-guide.html)
- **963 Manufacturer Codes Directory (NASA RP-1124 Appendix A)**: [`https://oht8woowi8yait9n.github.io/outgassing/manufacturers.html`](https://oht8woowi8yait9n.github.io/outgassing/manufacturers.html)
- **Structured JSONL Dataset (`13,582` records)**: [`outgassing_records.jsonl`](outgassing_records.jsonl)
- **Raw Upstream CSV (`13,582` rows)**: [`OutgassingData-CSV.csv`](OutgassingData-CSV.csv)

---

## 🛠️ Why a Pre-Rendered Static HTML Mirror is Required

The upstream `https://outgassing.nasa.gov/` portal redirects to a WordPress interactive DataTables page (`https://etd.gsfc.nasa.gov/capabilities/outgassing-database/`) that loads its `13,582` material rows dynamically via client-side JavaScript (`POST /wp-admin/admin-ajax.php?action=load_nasa_data`). Standard web/sitemap crawlers indexing `https://outgassing.nasa.gov/` only see an empty HTML table skeleton.

`generate_outgassing_sitemap.py` harvests both the raw WordPress CSV (`OutgassingData-CSV.csv`) and the `admin-ajax.php` JSON endpoint, resolves all 3-letter manufacturer codes against NASA Reference Publication 1124 Appendix A (`manufacturer_codes.json`), reconstructs multi-step cure schedules (Time, Temperature in $^\circ\text{C}$, Atmosphere across Steps 1–4), evaluates each test against NASA's standard low-outgassing screening criteria ($\text{TML} \le 1.0\%$, $\text{CVCM} \le 0.10\%$), and renders **146 self-contained HTML category pages** (`100` records per page) for fast, deterministic RAG indexing.

---

## 🚀 Usage

```bash
pip install -r requirements.txt
python3 generate_outgassing_sitemap.py
```
