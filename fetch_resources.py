import urllib.request
import re

# Get PhysioNet Challenge 2019 page
url = 'https://physionet.org/content/challenge-2019/1.0.0/'
resp = urllib.request.urlopen(url, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')

# Find data files
files = re.findall(r'href="([^"]+\.(?:csv|txt|zip|tar\.gz))"', html)
print(f'Challenge 2019 files: {files}')

# Find description
if 'training' in html.lower():
    print('Has training data')
if 'outcome' in html.lower() or 'label' in html.lower():
    print('Has outcome labels')

# Get GitHub Actions CI template
url2 = 'https://raw.githubusercontent.com/actions/starter-workflows/main/ci/python-package.yml'
resp2 = urllib.request.urlopen(url2, timeout=10)
ci_content = resp2.read().decode('utf-8', errors='ignore')
print(f'\nCI template length: {len(ci_content)} chars')
print(ci_content[:500])