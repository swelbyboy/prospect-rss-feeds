"""
GitHub Pages publisher module.
Handles publishing RSS feeds to GitHub Pages repository.
"""

import csv
import os
import shutil
from datetime import datetime
from git import Repo, GitCommandError
from config import Config


class GitHubPublisher:
    """Manages publishing RSS feeds to GitHub Pages."""

    def __init__(self):
        """Initialize the GitHub publisher."""
        self.repo_dir = Config.GITHUB_PAGES_DIR
        self.is_ci = os.getenv('GITHUB_CI') == 'true'
        # Only build repo URL if not in CI mode (CI uses workflow for commits)
        if not self.is_ci:
            self.repo_url = self._build_repo_url()
        else:
            self.repo_url = None
        self.repo = None

    def _build_repo_url(self):
        """Build the authenticated GitHub repository URL."""
        if not Config.GITHUB_TOKEN or not Config.GITHUB_USERNAME:
            raise ValueError("GITHUB_TOKEN and GITHUB_USERNAME must be set for GitHub publishing")
        return (
            f"https://{Config.GITHUB_TOKEN}@github.com/"
            f"{Config.GITHUB_USERNAME}/{Config.GITHUB_REPO_NAME}.git"
        )

    def setup_repository(self):
        """
        Clone or update the GitHub Pages repository.
        If the repository doesn't exist locally, it will be cloned.
        If it exists, it will be updated with the latest changes.
        """
        if os.path.exists(self.repo_dir):
            print(f"📁 Repository already exists at {self.repo_dir}")
            print("🔄 Pulling latest changes...")
            self.repo = Repo(self.repo_dir)
            try:
                origin = self.repo.remote(name='origin')
                origin.pull()
                print("✅ Repository updated successfully")
            except GitCommandError as e:
                print(f"⚠️  Warning: Could not pull latest changes: {e}")
        else:
            print(f"📥 Cloning repository to {self.repo_dir}...")
            try:
                self.repo = Repo.clone_from(self.repo_url, self.repo_dir)
                print("✅ Repository cloned successfully")
            except GitCommandError as e:
                print(f"❌ Error cloning repository: {e}")
                print("\n💡 Make sure:")
                print("   1. The repository exists on GitHub")
                print("   2. Your GitHub token has the correct permissions")
                print("   3. You've created the repository first")
                raise

    def create_repository_on_github(self):
        """
        Instructions for creating the GitHub Pages repository.
        This method doesn't create the repo automatically but provides guidance.
        """
        instructions = f"""
        📋 To create your GitHub Pages repository:

        1. Go to https://github.com/new
        2. Repository name: {Config.GITHUB_REPO_NAME}
        3. Make it Public (required for free GitHub Pages)
        4. Initialize with a README (optional)
        5. Click "Create repository"

        6. Enable GitHub Pages:
           - Go to Settings > Pages
           - Source: Deploy from a branch
           - Branch: main (or master)
           - Folder: / (root)
           - Click Save

        Your feeds will be available at:
        {Config.get_rss_base_url()}/<feed-name>.xml

        Run this script again after creating the repository.
        """
        print(instructions)

    def publish_feeds(self, feeds_dir=None):
        """
        Publish RSS feeds to GitHub Pages.

        Args:
            feeds_dir (str): Directory containing RSS feed files.
                           Defaults to Config.FEEDS_DIR.

        Returns:
            bool: True if publishing was successful, False otherwise
        """
        if feeds_dir is None:
            feeds_dir = Config.FEEDS_DIR

        if not os.path.exists(feeds_dir):
            print(f"❌ Feeds directory not found: {feeds_dir}")
            return False

        if self.repo is None:
            self.setup_repository()

        # Copy RSS feeds to repository
        print(f"📄 Copying RSS feeds from {feeds_dir}...")
        feed_files = [f for f in os.listdir(feeds_dir) if f.endswith('.xml')]

        if not feed_files:
            print("⚠️  No RSS feed files found to publish")
            return False

        for feed_file in feed_files:
            src_path = os.path.join(feeds_dir, feed_file)
            dst_path = os.path.join(self.repo_dir, feed_file)
            shutil.copy2(src_path, dst_path)
            print(f"   ✓ Copied {feed_file}")

        # Create/update index.html for easy browsing
        self._create_index_page(feed_files)

        # Commit and push changes
        return self._commit_and_push(feed_files)

    def _create_index_page(self, feed_files):
        """
        Create an index.html page listing all RSS feeds with status.

        Args:
            feed_files (list): List of RSS feed filenames
        """
        # Read tracking data
        tracking_data = []
        if os.path.exists(Config.TRACKING_CSV):
            with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                tracking_data = list(reader)

        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prospect RSS Feeds</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            max-width: 1200px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 30px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .success {
            color: green;
        }
        .failed {
            color: red;
        }
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
    
    <button class="upload-cta" onclick="openUploadModal()">📤 Upload New Prospects</button>

    <div id="uploadModal" class="upload-modal">
        <div class="modal-content">
            <span class="close" onclick="closeUploadModal()">&times;</span>
            <h2>Upload New Prospects</h2>
            <p>Upload a CSV file with columns: <strong>Prospect Name</strong> and <strong>Domain</strong></p>
            <form id="csvForm" onsubmit="submitCSV(event)">
                <div class="form-group">
                    <label for="csvContent">CSV Content:</label>
                    <textarea id="csvContent" name="csvContent" required placeholder="Prospect Name,Domain
TechCorp,techcorp.com
InnovateLabs,innovatelabs.io"></textarea>
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
            <th>RSS Feed</th>
            <th>Data Source</th>
            <th>Last Scrape Status</th>
            <th>Last Scrape Timestamp</th>
        </tr>
"""

        base_url = Config.get_rss_base_url()

        # Add rows from tracking data
        for entry in tracking_data:
            company_name = entry.get('company_name', '')
            status = entry.get('status', '')
            rss_url = entry.get('rss_url', '')
            last_scrape_date = entry.get('last_scrape_date', '-')
            data_source = entry.get('data_source', 'RSS')

            status_class = 'success' if status == 'success' else 'failed'

            if rss_url:
                rss_link = f'<a href="{rss_url}">{rss_url}</a>'
            else:
                rss_link = '-'

            html_content += f"""        <tr>
            <td>{company_name}</td>
            <td>{rss_link}</td>
            <td>{data_source}</td>
            <td class="{status_class}">{status}</td>
            <td>{last_scrape_date}</td>
        </tr>
"""

        html_content += f"""    </table>
    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    
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

        // Create GitHub issue URL with CSV content
        // Label will be auto-created by workflow if it doesn't exist
        const repoOwner = 'swelbyboy';
        const repoName = 'prospect-rss-feeds';
        const issueTitle = 'Upload new prospects CSV';
        const issueBody = '**CSV Content:**\\n\\n```\\n' + csvContent + '\\n```\\n\\n<!-- This issue will be automatically processed -->';
        const issueUrl = 'https://github.com/' + repoOwner + '/' + repoName + '/issues/new?title=' + encodeURIComponent(issueTitle) + '&body=' + encodeURIComponent(issueBody) + '&labels=new-prospects-csv';

        // Open in new window (label will be auto-created if needed)
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
</html>
"""

        index_path = os.path.join(self.repo_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"   ✓ Created index.html")

    def _commit_and_push(self, feed_files):
        """
        Commit and push changes to GitHub.

        Args:
            feed_files (list): List of RSS feed filenames

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Stage all changes
            self.repo.git.add(A=True)

            # Check if there are changes to commit
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                print("ℹ️  No changes to commit")
                return True

            # Commit changes
            commit_message = f"Update RSS feeds - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nUpdated {len(feed_files)} feed(s)"
            self.repo.index.commit(commit_message)
            print(f"✅ Committed changes: {len(feed_files)} feed(s)")

            # Push to GitHub
            print("📤 Pushing to GitHub...")
            origin = self.repo.remote(name='origin')
            origin.push()
            print("✅ Successfully pushed to GitHub Pages")

            # Display feed URLs
            print("\n📡 Your RSS feeds are now live:")
            base_url = Config.get_rss_base_url()
            for feed_file in sorted(feed_files):
                print(f"   • {base_url}/{feed_file}")

            print(f"\n🌐 View all feeds at: {base_url}/")

            return True

        except GitCommandError as e:
            print(f"❌ Error publishing to GitHub: {e}")
            return False


if __name__ == "__main__":
    # Test the GitHub publisher
    publisher = GitHubPublisher()

    print("Testing GitHub Publisher...")
    print("\nRepository setup instructions:")
    publisher.create_repository_on_github()
