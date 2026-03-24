#!/usr/bin/env python3
"""
Generate index.html from tracking.csv (primary source) plus any XML files
not already in tracking. This ensures all processed prospects are listed.
"""
import csv
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

# Generate index.html
html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prospect RSS Feeds</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; max-width: 1200px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .success { color: green; }
        .failed { color: red; }
        .upload-cta {
            background-color: #007bff;
            color: white;
            padding: 15px 30px;
            border-radius: 6px;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 30px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            cursor: pointer;
        }
        .upload-cta:hover {
            background-color: #0056b3;
        }
        .upload-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 30px;
            border: 1px solid #888;
            width: 90%;
            max-width: 600px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: black;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
            font-family: monospace;
            min-height: 200px;
        }
        .form-help {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .submit-btn {
            background-color: #28a745;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .submit-btn:hover {
            background-color: #218838;
        }
        .message {
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            display: none;
        }
        .success-message {
            background-color: #d4edda;
            color: #155724;
        }
        .error-message {
            background-color: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <h1>Prospect RSS Feeds</h1>
    <p>Total feeds: ''' + str(len(feed_entries)) + ''' &nbsp;·&nbsp; Last updated: ''' + datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC') + '''</p>
    
    <button class="upload-cta" onclick="openUploadModal()">📤 Upload New Prospects</button>

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
    <table>
        <tr>
            <th>Prospect Name</th>
            <th>Domain</th>
            <th>RSS Feed</th>
            <th>Last Scrape Status</th>
            <th>Last Scrape Timestamp</th>
        </tr>
'''

for entry in feed_entries:
    status_class = 'success' if entry['status'] == 'success' else 'failed'
    rss_link = f'<a href="{entry["url"]}">{entry["url"]}</a>'
    domain = entry.get('domain', '-')
    html += f'        <tr><td>{entry["name"]}</td><td>{domain}</td><td>{rss_link}</td><td class="{status_class}">{entry["status"]}</td><td>{entry["date"]}</td></tr>\n'

html += '''    </table>
    
    <script>
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
        if (event.target == modal) {{
            closeUploadModal();
        }}
    }}
    
    function submitCSV(event) {{
        event.preventDefault();
        const csvContent = document.getElementById('csvContent').value.trim();
        
        if (!csvContent) {{
            showMessage('Please enter CSV content', 'error');
            return;
        }}
        
        // Create GitHub issue directly via API (no manual label selection needed)
        // The label will be automatically created by the workflow if it doesn't exist
        const repoOwner = 'swelbyboy';
        const repoName = 'prospect-rss-feeds';
        const issueTitle = 'Upload new prospects CSV';
        const issueBody = '**CSV Content:**\\n\\n```\\n' + csvContent + '\\n```\\n\\n<!-- This issue will be automatically processed -->';

        // Create issue URL with label pre-selected
        const issueUrl = 'https://github.com/' + repoOwner + '/' + repoName + '/issues/new?title=' + encodeURIComponent(issueTitle) + '&body=' + encodeURIComponent(issueBody) + '&labels=new-prospects-csv';
        
        // Open in new window (will auto-create label if needed)
        window.open(issueUrl, '_blank');
        
        showMessage('✅ Opening GitHub to create issue. The label will be created automatically. After you submit, prospects will be added automatically.', 'success');
        
        // Reset form after a delay
        setTimeout(() => {{
            document.getElementById('csvForm').reset();
            closeUploadModal();
        }}, 2000);
    }}
    
    function showMessage(text, type) {{
        const messageDiv = document.getElementById('message');
        messageDiv.textContent = text;
        messageDiv.className = 'message ' + type + '-message';
        messageDiv.style.display = 'block';
    }}
    </script>
</body>
</html>'''

# Write to file
with open(Config.INDEX_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Generated index.html with {len(feed_entries)} feeds')

