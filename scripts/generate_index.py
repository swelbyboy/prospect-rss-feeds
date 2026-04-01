#!/usr/bin/env python3
"""
Generate index.html from tracking.csv (primary source) plus any XML files
not already in tracking. This ensures all processed prospects are listed.
"""
import csv
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from datetime import datetime

BASE_URL = 'https://swelbyboy.github.io/prospect-rss-feeds'

# Build feed entries from tracking.csv (primary source)
feed_entries = []
seen_urls = set()

try:
    with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            rss_url = entry.get('rss_url', '').strip()
            # Skip entries with no URL or the catch-all .xml bug URL
            if not rss_url or rss_url.endswith('/.xml'):
                continue
            if rss_url in seen_urls:
                continue
            seen_urls.add(rss_url)

            domain = entry.get('domain', '') or '-'
            company_name = entry.get('company_name', '').strip() or domain
            feed_entries.append({
                'name': company_name,
                'url': rss_url,
                'status': entry.get('status', '-'),
                'date': entry.get('last_scrape_date', '-'),
                'domain': domain,
            })
except FileNotFoundError:
    pass

# Also pick up any XML files on disk not already accounted for
xml_files = set()
if os.path.exists(Config.FEEDS_DIR):
    for f in os.listdir(Config.FEEDS_DIR):
        if f.endswith('.xml') and f != '.xml':
            xml_files.add(f)
for f in os.listdir(Config.PROJECT_ROOT):
    if f.endswith('.xml') and f != '.xml':
        xml_files.add(f)

for xml_file in sorted(xml_files):
    feed_url = f'{BASE_URL}/{xml_file}'
    if feed_url in seen_urls:
        continue
    seen_urls.add(feed_url)
    company_name = xml_file.replace('.xml', '').replace('-', ' ').title()
    feed_entries.append({
        'name': company_name,
        'url': feed_url,
        'status': 'success',
        'date': '-',
        'domain': '-',
    })

print(f'Generated {len(feed_entries)} feed entries')

# Serialize feed data as JSON for client-side rendering
feeds_json = json.dumps(feed_entries, separators=(',', ':'))
last_updated = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prospect RSS Feeds</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; max-width: 1200px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; word-break: break-all; }}
        th {{ background-color: #f2f2f2; }}
        .success {{ color: green; }}
        .failed {{ color: red; }}
        .pagination {{
            display: flex; align-items: center; gap: 8px; margin: 16px 0;
            flex-wrap: wrap;
        }}
        .pagination button {{
            padding: 6px 12px; border: 1px solid #ccc; background: #fff;
            cursor: pointer; border-radius: 4px;
        }}
        .pagination button:hover {{ background: #f0f0f0; }}
        .pagination button:disabled {{ opacity: 0.4; cursor: default; }}
        .pagination button.active {{ background: #007bff; color: white; border-color: #007bff; }}
        .pagination span {{ color: #555; }}
        .search-bar {{ margin-bottom: 16px; }}
        .search-bar input {{
            width: 100%; max-width: 400px; padding: 8px 12px;
            border: 1px solid #ccc; border-radius: 4px; font-size: 14px;
        }}
        .upload-cta {{
            background-color: #007bff; color: white; padding: 12px 24px;
            border-radius: 6px; text-decoration: none; display: inline-block;
            margin-bottom: 20px; font-size: 15px; font-weight: bold;
            border: none; cursor: pointer;
        }}
        .upload-cta:hover {{ background-color: #0056b3; }}
        .upload-modal {{
            display: none; position: fixed; z-index: 1000;
            left: 0; top: 0; width: 100%; height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        .modal-content {{
            background-color: #fefefe; margin: 5% auto; padding: 30px;
            border: 1px solid #888; width: 90%; max-width: 600px;
            border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .close {{ color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }}
        .close:hover {{ color: black; }}
        .form-group {{ margin-bottom: 20px; }}
        .form-group label {{ display: block; margin-bottom: 8px; font-weight: bold; }}
        .form-group textarea {{
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px;
            box-sizing: border-box; font-family: monospace; min-height: 200px;
        }}
        .form-help {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .submit-btn {{
            background-color: #28a745; color: white; padding: 10px 20px;
            border: none; border-radius: 4px; cursor: pointer; font-size: 16px;
        }}
        .submit-btn:hover {{ background-color: #218838; }}
        .message {{ padding: 10px; border-radius: 4px; margin-top: 10px; display: none; }}
        .success-message {{ background-color: #d4edda; color: #155724; }}
        .error-message {{ background-color: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <h1>Prospect RSS Feeds</h1>
    <p id="summary">Loading...</p>
    <p style="color:#888;font-size:13px;">Last updated: {last_updated}</p>

    <button class="upload-cta" onclick="openUploadModal()">&#128228; Upload New Prospects</button>

    <div id="uploadModal" class="upload-modal">
        <div class="modal-content">
            <span class="close" onclick="closeUploadModal()">&times;</span>
            <h2>Upload New Prospects</h2>
            <p>Upload a CSV file with columns: <strong>Prospect Name</strong> and <strong>Domain</strong></p>
            <form id="csvForm" onsubmit="submitCSV(event)">
                <div class="form-group">
                    <label for="csvContent">CSV Content:</label>
                    <textarea id="csvContent" name="csvContent" required placeholder="Prospect Name,Domain&#10;TechCorp,techcorp.com&#10;InnovateLabs,innovatelabs.io"></textarea>
                    <div class="form-help">Paste your CSV data here. Format: Prospect Name,Domain (one per line)</div>
                </div>
                <button type="submit" class="submit-btn">Submit</button>
                <div id="message" class="message"></div>
            </form>
        </div>
    </div>

    <h2>Current Prospects</h2>
    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="Search by name or domain..." oninput="onSearch()">
    </div>
    <div id="paginationTop" class="pagination"></div>
    <table>
        <thead>
            <tr>
                <th>Prospect Name</th>
                <th>Domain</th>
                <th>RSS Feed</th>
                <th>Status</th>
                <th>Last Scrape</th>
            </tr>
        </thead>
        <tbody id="feedTable"></tbody>
    </table>
    <div id="paginationBottom" class="pagination"></div>

    <script>
    const ALL_FEEDS = {feeds_json};
    const PAGE_SIZE = 100;
    let filtered = ALL_FEEDS;
    let currentPage = 1;

    document.getElementById('summary').textContent =
        'Total feeds: ' + ALL_FEEDS.length.toLocaleString();

    function onSearch() {{
        const q = document.getElementById('searchInput').value.toLowerCase().trim();
        filtered = q ? ALL_FEEDS.filter(f =>
            (f.name && f.name.toLowerCase().includes(q)) ||
            (f.domain && f.domain.toLowerCase().includes(q))
        ) : ALL_FEEDS;
        currentPage = 1;
        render();
    }}

    function render() {{
        const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
        if (currentPage > totalPages) currentPage = totalPages;
        const start = (currentPage - 1) * PAGE_SIZE;
        const slice = filtered.slice(start, start + PAGE_SIZE);

        const tbody = document.getElementById('feedTable');
        tbody.innerHTML = slice.map(f => {{
            const cls = f.status === 'success' ? 'success' : 'failed';
            return '<tr><td>' + esc(f.name) + '</td><td>' + esc(f.domain) +
                   '</td><td><a href="' + esc(f.url) + '">' + esc(f.url) + '</a></td>' +
                   '<td class="' + cls + '">' + esc(f.status) + '</td><td>' + esc(f.date) + '</td></tr>';
        }}).join('');

        renderPagination('paginationTop', totalPages);
        renderPagination('paginationBottom', totalPages);
    }}

    function renderPagination(id, totalPages) {{
        const el = document.getElementById(id);
        if (totalPages <= 1) {{ el.innerHTML = ''; return; }}

        const info = '<span>Page ' + currentPage + ' of ' + totalPages +
                     ' (' + filtered.length.toLocaleString() + ' feeds)</span>';

        let pages = '';
        const delta = 2;
        let prev = Math.max(1, currentPage - delta);
        let next = Math.min(totalPages, currentPage + delta);
        if (prev > 1) pages += btn(1, totalPages) + (prev > 2 ? '<span>...</span>' : '');
        for (let p = prev; p <= next; p++) pages += btn(p, totalPages);
        if (next < totalPages) pages += (next < totalPages - 1 ? '<span>...</span>' : '') + btn(totalPages, totalPages);

        el.innerHTML =
            '<button onclick="goPage(' + (currentPage-1) + ')" ' + (currentPage===1?'disabled':'') + '>&laquo; Prev</button>' +
            pages +
            '<button onclick="goPage(' + (currentPage+1) + ')" ' + (currentPage===totalPages?'disabled':'') + '>Next &raquo;</button>' +
            info;
    }}

    function btn(p, totalPages) {{
        const active = p === currentPage ? ' active' : '';
        return '<button class="' + active + '" onclick="goPage(' + p + ')">' + p + '</button>';
    }}

    function goPage(p) {{
        const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
        currentPage = Math.max(1, Math.min(p, totalPages));
        render();
        window.scrollTo(0, 0);
    }}

    function esc(s) {{
        if (!s) return '-';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}

    function openUploadModal() {{
        document.getElementById('uploadModal').style.display = 'block';
    }}

    function closeUploadModal() {{
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('csvForm').reset();
        document.getElementById('message').style.display = 'none';
    }}

    window.onclick = function(event) {{
        const modal = document.getElementById('uploadModal');
        if (event.target == modal) closeUploadModal();
    }}

    function submitCSV(event) {{
        event.preventDefault();
        const csvContent = document.getElementById('csvContent').value.trim();
        if (!csvContent) {{ showMessage('Please enter CSV content', 'error'); return; }}
        const repoOwner = 'swelbyboy';
        const repoName = 'prospect-rss-feeds';
        const issueTitle = 'Upload new prospects CSV';
        const issueBody = '**CSV Content:**\\n\\n```\\n' + csvContent + '\\n```\\n\\n<!-- This issue will be automatically processed -->';
        const issueUrl = 'https://github.com/' + repoOwner + '/' + repoName +
            '/issues/new?title=' + encodeURIComponent(issueTitle) +
            '&body=' + encodeURIComponent(issueBody) + '&labels=new-prospects-csv';
        window.open(issueUrl, '_blank');
        showMessage('Opening GitHub to create issue. Prospects will be added automatically.', 'success');
        setTimeout(() => {{ document.getElementById('csvForm').reset(); closeUploadModal(); }}, 2000);
    }}

    function showMessage(text, type) {{
        const d = document.getElementById('message');
        d.textContent = text;
        d.className = 'message ' + type + '-message';
        d.style.display = 'block';
    }}

    render();
    </script>
</body>
</html>'''

# Write to file
with open(Config.INDEX_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Generated index.html with {len(feed_entries)} feeds')
