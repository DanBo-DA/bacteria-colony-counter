#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path


def bump_version():
    pkg_path = Path('frontend/package.json')
    data = json.loads(pkg_path.read_text())
    version = data.get('version', '0.0.0')
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f'Unsupported version format: {version}')
    major, minor, patch = map(int, parts)
    patch += 1
    new_version = f"{major}.{minor}.{patch}"
    data['version'] = new_version
    pkg_path.write_text(json.dumps(data, indent=2) + '\n')

    for backend_file in ['backend/main.py', 'backend/mainCS.py']:
        path = Path(backend_file)
        text = path.read_text()
        text = re.sub(r'version="[0-9.]+"', f'version="{new_version}"', text)
        path.write_text(text)

    subprocess.run(['git', 'add', 'frontend/package.json', 'backend/main.py', 'backend/mainCS.py'], check=True)
    subprocess.run(['git', 'commit', '--no-verify', '-m', 'Bump version'], check=True)


if __name__ == '__main__':
    bump_version()
