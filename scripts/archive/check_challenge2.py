import urllib.request
import re

# Check for outcomes file
url = 'https://physionet.org/files/challenge-2019/1.0.0/training/'
resp = urllib.request.urlopen(url, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')
files = re.findall(r'href="([^"]+\.(?:csv|txt|psv))"', html)
print(f'Training dir files: {files}')

# Check training_setB
url2 = 'https://physionet.org/files/challenge-2019/1.0.0/training/training_setB/'
resp2 = urllib.request.urlopen(url2, timeout=10)
html2 = resp2.read().decode('utf-8', errors='ignore')
files2 = re.findall(r'href="([^"]+\.(?:psv))"', html2)
print(f'Training setB files: {len(files2)}')