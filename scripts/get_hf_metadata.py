import socket
old = socket.getaddrinfo
socket.getaddrinfo = lambda *args, **kwargs: [r for r in old(*args, **kwargs) if r[0] == socket.AF_INET]
from huggingface_hub import HfApi
api = HfApi()

for repo in ['Comfy-Org/vae-text-encorder-for-flux-klein-4b', 'black-forest-labs/FLUX.2-klein-4b-fp8']:
    info = api.model_info(repo, files_metadata=True)
    print(f"Repo: {repo}")
    for s in info.siblings:
        if s.lfs:
            print(f"  {s.rfilename} -> sha256={s.lfs.get('sha256')} size={s.lfs.get('size')}")
