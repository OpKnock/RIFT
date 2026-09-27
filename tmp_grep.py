t = open("frontend/src/components/twin-3d.tsx", encoding="utf-8", errors="replace").read()
for l in t.splitlines():
    if "ts-" in l or "@ts" in l or "tsc" in l or "eslint-disable" in l:
        print(l.strip()[:100])
print("done")
