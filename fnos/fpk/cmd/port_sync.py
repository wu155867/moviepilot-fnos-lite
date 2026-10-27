#!/usr/bin/env python3
"""把服务端口同步到 fnOS 系统侧的三处登记。

用法: port_sync.py <port> <appname> <target_dir> <app_root_dir>

三处登记（缺一处点击桌面图标就会打不开）：
  1. <target>/ui/config          桌面入口的 port 字段
  2. <app_root>/manifest         service_port（appcenter 启动时读它注入 TRIM_SERVICE_PORT）
  3. PostgreSQL appcenter 库      app_service.url / default_url（应用中心「访问」与桌面快捷方式）
仅 root 可执行，非 root 时直接跳过。
"""
import datetime
import json
import os
import re
import subprocess
import sys


def log(msg):
    print("[%s] %s" % (datetime.datetime.now().isoformat(timespec="seconds"), msg), flush=True)


def sync_ui(target, port):
    path = os.path.join(target, "ui", "config")
    if not os.path.isfile(path):
        return "ui/config 不存在，跳过"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return "ui/config 解析失败: %s" % exc
    dirty = False
    for ent in (data.get(".url") or {}).values():
        if isinstance(ent, dict) and ent.get("port") != port:
            ent["port"] = port
            dirty = True
    if not dirty:
        return "ui/config 已是 %d" % port
    st = os.stat(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")
    os.chmod(tmp, st.st_mode & 0o777)
    try:
        os.chown(tmp, st.st_uid, st.st_gid)
    except PermissionError:
        pass
    os.replace(tmp, path)
    return "ui/config → %d" % port


def sync_manifest(app_root, port):
    path = os.path.join(app_root, "manifest")
    if not os.path.isfile(path):
        return "manifest 不存在，跳过"
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    dirty = False
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*service_port\s*=\s*)(\d+)", line)
        if m and int(m.group(2)) != port:
            lines[i] = "%s%d\n" % (m.group(1), port)
            dirty = True
    if not dirty:
        return "manifest 已是 %d" % port
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return "manifest → %d" % port


def psql(sql):
    return subprocess.run(
        ["su", "postgres", "-s", "/bin/sh", "-c", "psql -d appcenter -Atq -f -"],
        input=sql, text=True, capture_output=True, timeout=40,
    )


def sync_db(app, port):
    probe = ("SELECT url FROM app_service WHERE app_id = "
             "(SELECT id FROM app WHERE app_name = '%s');" % app)
    r = psql(probe)
    if r.returncode != 0:
        return "数据库查询失败: %s" % (r.stderr or "").strip()[:160]
    urls = [u.strip() for u in r.stdout.splitlines() if u.strip()]
    if not urls:
        return "数据库暂无该应用记录（安装阶段属正常）"
    pattern = re.compile(r":%d/" % port)
    if all(pattern.search(u) for u in urls):
        return "数据库 URL 已是 :%d" % port
    if not any(re.search(r":[0-9]+/", u) for u in urls):
        return "数据库 URL 无端口段，需人工确认: %s" % urls[0]
    upd = (
        "UPDATE app_service SET "
        "url = regexp_replace(url, ':[0-9]+/', ':{p}/'), "
        "default_url = regexp_replace(default_url, ':[0-9]+/', ':{p}/'), "
        "updated_at = now() "
        "WHERE app_id = (SELECT id FROM app WHERE app_name = '{a}') "
        "AND url ~ ':[0-9]+/';".format(p=port, a=app)
    )
    r = psql(upd)
    if r.returncode != 0:
        return "数据库更新失败: %s" % (r.stderr or "").strip()[:160]
    return "数据库 URL → :%d" % port


def main():
    if len(sys.argv) < 5:
        log("参数不足，用法: port_sync.py <port> <appname> <target> <app_root>")
        return 2
    port = int(sys.argv[1])
    app = sys.argv[2]
    target = sys.argv[3]
    app_root = sys.argv[4]
    if os.geteuid() != 0:
        log("当前非 root，跳过系统侧登记同步")
        return 0
    for fn, args in ((sync_ui, (target, port)),
                     (sync_manifest, (app_root, port)),
                     (sync_db, (app, port))):
        try:
            log(fn(*args))
        except Exception as exc:
            log("%s 异常: %s" % (fn.__name__, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
