import urllib.request
import re

# Check challenge 2019 training data
url = 'https://physionet.org/files/challenge-2019/1.0.0/training/'
resp = urllib.request.urlopen(url, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')

files = re.findall(r'href="([^"]+\.(?:csv|txt|zip|tar\.gz|psv))"', html)
print(f'Training files: {files}')

# Check training_setA
url2 = 'https://physionet.org/files/challenge-2019/1.0.0/training/training_setA/'
resp2 = urllib.request.urlopen(url2, timeout=10)
html2 = resp2.read().decode('utf-8', errors='ignore')
files2 = re.findall(r'href="([^"]+\.(?:csv|txt|psv))"', html2)
print(f'Training setA files: {len(files2)} files')
if files2:
    print(f'  First 5: {files2[:5]}')