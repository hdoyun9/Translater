"""Download inert, pinned CTranslate2 model data; never execute repository code."""
import hashlib,json
from pathlib import Path
import urllib.request
stage=Path(__file__).resolve().parents[1]
repo='jncraton/m2m100_418M-ct2-int8'
with urllib.request.urlopen('https://huggingface.co/api/models/'+repo,timeout=30) as response:
    revision=json.load(response)['sha']
folder=stage/'models'/'m2m100'
(folder/'model').mkdir(parents=True,exist_ok=True)
files={'model.bin':'model/model.bin','config.json':'model/config.json',
       'shared_vocabulary.json':'model/shared_vocabulary.json','sentencepiece.bpe.model':'sentencepiece.model'}
manifest={'repository':repo,'revision':revision,'license':'MIT','files':[]}
for remote,relative in files.items():
    target=folder/relative
    if not target.exists():
        url=f'https://huggingface.co/{repo}/resolve/{revision}/{remote}'
        print('Downloading',remote,flush=True)
        with urllib.request.urlopen(url,timeout=60) as response,target.with_suffix(target.suffix+'.part').open('wb') as output:
            total=0; bucket=-1
            while True:
                data=response.read(1024*1024)
                if not data: break
                output.write(data); total+=len(data)
                if total//(100*1024*1024)!=bucket:
                    bucket=total//(100*1024*1024);print(total//1048576,'MB',flush=True)
        target.with_suffix(target.suffix+'.part').replace(target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if remote=='model.bin' and digest!='d6703dd9f920ff896e45c3d97b490761bed5944937b90bbe6a7245f5652542d4':
        raise ValueError('Unexpected model checksum')
    manifest['files'].append({'file':relative,'sha256':digest})
(folder/'metadata.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2),flush=True)
