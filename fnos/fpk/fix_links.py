import os, sys
D = sys.argv[1]
OLD = "/vol1/1000/apps/mp-app"
fixed, skipped = 0, []
for root, dirs, files in os.walk(D):
    for name in files + dirs:
        p = os.path.join(root, name)
        if os.path.islink(p):
            t = os.readlink(p)
            if t.startswith(OLD):
                inner = t[len(OLD):].lstrip("/")          # path relative to app root
                rel = os.path.relpath(os.path.join(D, inner), root)
                os.remove(p); os.symlink(rel, p)
                fixed += 1
            elif os.path.isabs(t):
                skipped.append((p, t))
print("fixed:", fixed)
for p, t in skipped[:20]:
    print("ABS-SKIP:", p, "->", t)
print("abs_skipped:", len(skipped))
# pyvenv.cfg
cfg = os.path.join(D, ".venv-linux/pyvenv.cfg")
s = open(cfg).read()
s = s.replace(OLD + "/runtime/python/bin", "../../runtime/python/bin")
s = s.replace("command = /vol1/1000/apps/mp-app/runtime/python/bin/python3 -m venv /vol1/1000/apps/mp-app/.venv-linux",
              "command = runtime/python/bin/python3 -m venv .venv-linux (in-package)")
open(cfg, "w").write(s)
print(open(cfg).read())
