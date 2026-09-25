import urllib.request
import csv
import io

url = 'https://physionet.org/files/big-ideas-glycemic-wearable/1.0.0/Demographics.csv'
req = urllib.request.Request(url, headers={'Accept': 'text/csv'})
resp = urllib.request.urlopen(req, timeout=30)
text = resp.read().decode('utf-8', errors='ignore')

lines = text.splitlines()
reader = csv.DictReader(lines)
rows = list(reader)

with open('demographics_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'Columns: {reader.fieldnames}\n')
    f.write(f'Rows: {len(rows)}\n')
    for row in rows[:5]:
        f.write(str(row) + '\n')
print('Done - check demographics_output.txt')