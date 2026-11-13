"""Emit a selected research file for the connected GitHub upload tool.

This helper never reads credentials and never accepts paths outside this package.
"""
from pathlib import Path
import sys,json,hashlib,base64
root=Path(__file__).resolve().parents[1]
p=(root/sys.argv[1]).resolve()
assert p.is_relative_to(root) and p.is_file()
b=p.read_bytes()
print(json.dumps({'path':p.relative_to(root).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
                  'git_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),
                  'encoding':'base64','content':base64.b64encode(b).decode('ascii')},ensure_ascii=True))
