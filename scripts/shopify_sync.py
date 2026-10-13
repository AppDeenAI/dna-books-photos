"""Encrypted hand-off of a Shopify bulk-update file (runs in GitHub Actions).

  keygen  - make a one-time RSA key pair; the private key stays on the runner,
            the public key is committed to sync/pubkey.json
  wait    - poll the repo until sync/payload.enc (encrypted to that key) arrives
  run     - decrypt the payload, check the update file against its checksum,
            upload it to Shopify's staged-upload target, write sync/result.json

The payload carries the update file plus a short-lived signed upload URL. It is
encrypted to a key that only ever exists on this runner, so nothing readable
about the store is committed. No Shopify credentials touch this repo.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PRIV = '/tmp/sync_private_key.pem'


def sh(*args):
    subprocess.run(args, check=True)


def git_push(message, add=(), remove=()):
    if add:
        sh('git', 'add', *add)
    if remove:
        sh('git', 'rm', '-q', '--ignore-unmatch', *remove)
    sh('git', 'commit', '-m', message)
    for _ in range(5):
        if subprocess.run(['git', 'push']).returncode == 0:
            return
        sh('git', 'pull', '--rebase')
    raise SystemExit('push failed')


def keygen():
    req = json.load(open('sync/request.json'))
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    with open(PRIV, 'wb') as fh:
        fh.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    json.dump({'request_id': req['request_id'], 'public_key': pem}, open('sync/pubkey.json', 'w'), indent=1)
    git_push(f'Shopify sync {req["request_id"]}: one-time public key', add=['sync/pubkey.json'])


def wait():
    req = json.load(open('sync/request.json'))
    for _ in range(150):  # up to ~25 minutes
        subprocess.run(['git', 'pull', '-q', '--rebase'])
        if os.path.exists('sync/payload.enc'):
            env = json.load(open('sync/payload.enc'))
            if env.get('request_id') == req['request_id']:
                print('payload received')
                return
        time.sleep(10)
    raise SystemExit('timed out waiting for sync/payload.enc')


def decrypt():
    env = json.load(open('sync/payload.enc'))
    key = serialization.load_pem_private_key(open(PRIV, 'rb').read(), password=None)
    aes = key.decrypt(base64.b64decode(env['enc_key']),
                      padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    pt = AESGCM(aes).decrypt(base64.b64decode(env['nonce']), base64.b64decode(env['ct']),
                             env['request_id'].encode())
    payload = json.loads(pt)
    print(f'::add-mask::{payload["upload_url"]}')
    for p in payload['upload_params']:
        print(f'::add-mask::{p["value"]}')
    return payload


def run():
    payload = decrypt()
    body = payload['jsonl'].encode('utf-8')
    sha = hashlib.sha256(body).hexdigest()
    if sha != payload['jsonl_sha256']:
        raise SystemExit('update file checksum mismatch')
    lines = body.count(b'\n')

    form = [(p['name'], (None, p['value'])) for p in payload['upload_params']]
    form.append(('file', (payload.get('filename', 'updates.jsonl'), body, 'text/jsonl')))
    up = requests.post(payload['upload_url'], files=form, timeout=300)
    print('upload status', up.status_code)
    ok = up.status_code in (200, 201, 204)

    result = {'request_id': payload['request_id'], 'upload_status': up.status_code, 'uploaded': ok,
              'jsonl_sha256': sha, 'jsonl_lines': lines, 'jsonl_bytes': len(body)}
    if not ok:
        result['error'] = up.text[:300]
    json.dump(result, open('sync/result.json', 'w'), indent=1)
    git_push(f'Shopify sync {payload["request_id"]}: upload {"done" if ok else "failed"}',
             add=['sync/result.json'], remove=['sync/payload.enc'])
    print(json.dumps(result, indent=1))
    if not ok:
        raise SystemExit('upload failed')


if __name__ == '__main__':
    {'keygen': keygen, 'wait': wait, 'run': run}[sys.argv[1]]()
