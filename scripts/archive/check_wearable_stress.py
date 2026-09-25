import urllib.request
import re

# Check wearable-exam-stress dataset
url = 'https://physionet.org/files/wearable-exam-stress/1.0.0/'
req = urllib.request.Request(url, headers={'Accept': 'text/html'})
resp = urllib.request.urlopen(req, timeout=30)
html = resp.read().decode('utf-8', errors='ignore')

files = re.findall(r'href="([^"]+\.(?:csv|txt))"', html)
print(files)

# Check for subdirectories
dirs = re.findall(r'href="([^"/]+/)"', html)
print('Dirs:', dirs)