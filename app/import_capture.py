"""Offline capture importer. Never connects to a robot or sends photos to a provider.

python3 app/import_capture.py RUN --data-dir WORKSPACE
Use --indices 2,15,28 to select exact manifest frames after reviewing the shoot.
"""
import argparse
import base64
import json
from pathlib import Path
from server import Store, timestamp


def import_capture(run, destination, indices=None):
    run, destination = Path(run).resolve(), Path(destination).resolve()
    if (destination / 'watch.sqlite3').exists():
        raise ValueError('Choose a fresh workspace; existing data will not be overwritten.')
    manifest = json.loads((run / 'manifest.json').read_text())
    frames = manifest['frames']
    if not frames:
        raise ValueError('Capture contains no camera frames.')
    if indices is None:
        count = min(12, len(frames))
        indices = sorted({round(i * (len(frames) - 1) / max(1, count - 1)) for i in range(count)})
    entries = []
    for i in indices:
        if i < 0 or i >= len(frames):
            raise ValueError(f'Frame index {i} is out of range.')
        frame = frames[i]
        image = (run / frame['file']).resolve()
        if not image.is_relative_to(run):
            raise ValueError('Frame path escapes capture directory.')
        at = timestamp(frame['at'])
        entries.append((i, frame, image.read_bytes(), at))
    store = Store(destination)
    imported = []
    for i, frame, raw, at in entries:
        result = store.create_observation({
            'title': f'BenBen camera · frame {i}',
            'observed_at': at,
            'notes': f'Human-piloted capture. Recorder timestamp; not independently synchronized. Source: {frame["file"]}. Pose retained in source manifest; spatial registration not verified.',
            'image_base64': base64.b64encode(raw).decode(),
        })
        imported.append({'frame_index': i, 'file': frame['file'], 'observation_id': result['id']})
    receipt = {'capture': str(run), 'observations': imported,
               'map_available': bool(manifest.get('map')), 'map_imported': False,
               'note': 'Original video, clouds and pose stay in the capture. No issue or AI verdict is fabricated.'}
    (destination / 'capture-import.json').write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--indices', help='Comma-separated zero-based manifest frame indices')
    args = parser.parse_args()
    result = import_capture(args.run, args.data_dir,
                            [int(i) for i in args.indices.split(',')] if args.indices else None)
    print(f'Imported {len(result["observations"])} real frames. No provider request made.')
