"""Stage a separately named diagnostic worker from the retained history worker."""
from pathlib import Path
import argparse
import hashlib

OLD_SOURCE = '40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515'
NEW_SOURCE = 'd4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'


def stage(worker_directory: Path, source: Path) -> None:
    if hashlib.sha256(source.read_bytes()).hexdigest() != NEW_SOURCE:
        raise ValueError('Expected the qualified pre-split diagnostic source')
    checkpoint = (worker_directory / 'history-checkpoint.mjs').read_text()
    worker = (worker_directory / 'history-render.mjs').read_text()
    if checkpoint.count(OLD_SOURCE) != 1 or worker.count('./history-checkpoint.mjs') != 1:
        raise ValueError('Expected the retained history worker and checkpoint module')
    (worker_directory / 'presplit-checkpoint.mjs').write_text(checkpoint.replace(OLD_SOURCE, NEW_SOURCE))
    (worker_directory / 'presplit-render.mjs').write_text(worker.replace('./history-checkpoint.mjs', './presplit-checkpoint.mjs'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('worker_directory', type=Path)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    stage(args.worker_directory, args.source)
