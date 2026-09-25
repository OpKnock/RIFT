import urllib.request
import re

url = 'https://physionet.org/files/wearable-exam-stress/1.0.0/data/S1/'
req = urllib.request.Request(url, headers={'Accept': 'text/html'})
resp = urllib.request.urlopen(req, timeout=30)
html = resp.read().decode('utf-8', errors='ignore')

dirs = re.findall(r'href="([^"/]+/)"', html)
print('Dirs:', dirs)

# Check full HTML for any file links
files_all = re.findall(r'href="([^"]+)"', html)
for f in files_all:
    if not f.startswith('../'):
        print(f'  {f}')