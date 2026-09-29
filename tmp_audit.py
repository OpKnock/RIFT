t = open("frontend/src/pages/simulation.tsx", encoding="utf-8", errors="replace").read()
import re
for n, l in enumerate(t.splitlines()):
    if re.search(r"[Gg]uardian|WITHHOLD|withhold|verdict", l):
        print(n + 1, l.strip()[:140])
