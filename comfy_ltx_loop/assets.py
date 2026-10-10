import os
import re
from pathlib import Path
from urllib.request import urlopen

from .project import sha


def cache_weight(url, destination, expected_sha256):
    if not url.startswith('https://') or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('HTTPS URL and expected lowercase SHA-256 required')
    destination = Path(destination).resolve()
    if destination.exists():
        if sha(destination) != expected_sha256:
            raise ValueError('Cached weight differs; choose a new destination')
        return {'path': str(destination), 'sha256': expected_sha256, 'cached': True}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.download')
    with urlopen(url, timeout=60) as response, temporary.open('wb') as output:
        while block := response.read(1024 * 1024):
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
    if sha(temporary) != expected_sha256:
        raise ValueError('Weight checksum failed; partial download retained, not installed')
    os.replace(temporary, destination)
    return {'path': str(destination), 'sha256': expected_sha256, 'cached': False}
