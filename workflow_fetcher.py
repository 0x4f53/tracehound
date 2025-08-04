import requests
import base64
import os
import hashlib
import json
import sys
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

GITHUB_TOKENS = []
TRACKER_FILE = "cachetracker.json"

workers=25

# Ensure tracker file exists
if not os.path.exists(TRACKER_FILE):
    open(TRACKER_FILE, 'w', encoding='utf-8').close()

def load_tokens(token_file):
    global GITHUB_TOKENS
    with open(token_file, 'r', encoding='utf-8') as f:
        GITHUB_TOKENS = [line.strip() for line in f if line.strip()]

def get_headers():
    token = random.choice(GITHUB_TOKENS) if GITHUB_TOKENS else None
    return {
        "Authorization": f"token {token}" if token else None,
        "Accept": "application/vnd.github.v3+json"
    }

def get_commits_affecting_path(owner, repo, path):
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 100}
    response = requests.get(commits_url, headers=get_headers(), params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch commits for {owner}/{repo}/{path}: {response.status_code}")
        return []

def sha256_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def ensure_cache_dir(owner, repo):
    dir_path = os.path.join("cache", owner, repo)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

def get_cache_file_path(cache_dir, commit_sha, filename):
    return os.path.join(cache_dir, f"{commit_sha}_{filename}")

def load_from_cache(cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def append_to_tracker(metadata):
    with open(TRACKER_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(metadata) + "\n")

def get_file_content_at_commit(owner, repo, path, commit_sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": commit_sha}
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code == 200:
        content_data = response.json()
        files = []
        if isinstance(content_data, list):
            for item in content_data:
                if item['type'] == 'file':
                    file_response = requests.get(item['url'], headers=get_headers(), params={"ref": commit_sha})
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        if file_data.get('encoding') == 'base64':
                            content = base64.b64decode(file_data['content']).decode('utf-8')
                            files.append({
                                'name': file_data['name'],
                                'path': file_data['path'],
                                'sha': commit_sha,
                                'url': file_data['html_url'],
                                'content': content
                            })
        elif content_data.get('encoding') == 'base64':
            content = base64.b64decode(content_data['content']).decode('utf-8')
            files.append({
                'name': content_data['name'],
                'path': content_data['path'],
                'sha': commit_sha,
                'url': content_data['html_url'],
                'content': content
            })
        return files
    return []

def get_commit_metadata(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        data = response.json()
        return {
            "timestamp": data['commit']['author']['date'],
            "author_name": data['commit']['author']['name'],
            "author_email": data['commit']['author']['email'],
            "patch_url": data['html_url'] + ".patch"
        }
    return {
        "timestamp": "Unknown",
        "author_name": "Unknown",
        "author_email": "Unknown",
        "patch_url": ""
    }

def append_to_tracker(metadata):
    tracker_lock = threading.Lock()
    with tracker_lock:
        with open(TRACKER_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(metadata) + "\n")

def process_repo(repo_full_name):
    parts = repo_full_name.strip().split('/')
    if len(parts) < 2:
        print(f"Skipping invalid repo format: {repo_full_name}")
        return

    owner, repo = parts[0], parts[1]

    print(f"\n=== {repo_full_name} ===")
    cache_dir = ensure_cache_dir(owner, repo)

    commits = get_commits_affecting_path(owner, repo, ".github/workflows")
    seen_files = set()

    for commit in commits:
        sha = commit['sha']

        found_in_cache = False
        for filename in os.listdir(cache_dir):
            if filename.startswith(sha + "_"):
                file_path = os.path.join(cache_dir, filename)
                content = load_from_cache(file_path)
                if content:
                    print(f"\n--- {filename.split('_', 1)[1]} ---")
                    print(f"Commit: {sha}")
                    print(f"Cached from: {file_path}")
                    print(content)
                    found_in_cache = True
        if found_in_cache:
            continue

        metadata = get_commit_metadata(owner, repo, sha)
        files = get_file_content_at_commit(owner, repo, ".github/workflows", sha)
        for file_info in files:
            key = (file_info['path'], sha)
            if key in seen_files:
                continue
            seen_files.add(key)

            filename = file_info['name']
            cache_file_path = get_cache_file_path(cache_dir, sha, filename)

            with open(cache_file_path, 'w', encoding='utf-8') as f:
                f.write(file_info['content'])

            metadata.update({
                'repo': repo_full_name,
                'commit': sha,
                'file_name': filename,
                'url': file_info['url'],
                'cache_path': cache_file_path
            })
            append_to_tracker(metadata)

            print(f"\n--- {filename} ---")
            print(f"Commit: {sha}")
            print(f"URL: {file_info['url']}")
            print(file_info['content'])

def main():
    args = dict(arg.split('=') for arg in sys.argv[1:] if '=' in arg)

    if 'repolist' not in args or 'tokenlist' not in args:
        print("Usage: python script.py repolist=repolist.txt tokenlist=tokenlist.txt")
        sys.exit(1)

    repolist_path = args['repolist']
    tokenlist_path = args['tokenlist']
    load_tokens(tokenlist_path)

    with open(repolist_path, 'r', encoding='utf-8') as f:
        repos = [line.strip() for line in f if line.strip()]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_repo, repo_full_name) for repo_full_name in repos]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing repo: {e}")

if __name__ == "__main__":
    main()