import urllib.request
import re

url = 'https://physionet.org/files/wearable-exam-stress/1.0.0/data/'
req = urllib.request.Request(url, headers={'Accept': 'text/html'})
resp = urllib.request.urlopen(req, timeout=30)
html = resp.read().decode('utf-8', errors='ignore')

files = re.findall(r'href="([^"]+\.(?:csv|txt))"', html)
print(files)

dirs = re.findall(r'href="([^"/]+/)"', html)
print('Dirs:', dirs)