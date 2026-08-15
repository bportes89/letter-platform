import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def create_backup(destination:Path)->dict:
    destination.parent.mkdir(parents=True,exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        source=settings.database_url.removeprefix("sqlite:///")
        with sqlite3.connect(source) as src,sqlite3.connect(destination) as dst:src.backup(dst)
        kind="SQLITE"
    else:
        executable=shutil.which("pg_dump")
        if not executable:raise RuntimeError("pg_dump não encontrado")
        subprocess.run([executable,"--format=custom","--file",str(destination),settings.database_url.replace("+psycopg","")],check=True);kind="POSTGRESQL"
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest={"created_at":datetime.now(UTC).isoformat(),"database":kind,"file":destination.name,"size_bytes":destination.stat().st_size,"sha256":digest}
    destination.with_suffix(destination.suffix+".json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");return manifest


def verify_sqlite_backup(path:Path)->dict:
    with sqlite3.connect(path) as db:
        result=db.execute("PRAGMA integrity_check").fetchone()[0];tables=db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    return {"integrity":result,"tables":tables,"valid":result=="ok" and tables>0}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=["create","verify"]);parser.add_argument("path");args=parser.parse_args();path=Path(args.path)
    print(json.dumps(create_backup(path) if args.command=="create" else verify_sqlite_backup(path),ensure_ascii=False))

if __name__=="__main__":main()
