from pathlib import Path
_parts_dir = Path(__file__).resolve().parent / 'app_parts'
_source = ''.join(p.read_text(encoding='utf-8') for p in sorted(_parts_dir.glob('part*.pyfrag')))
exec(compile(_source, str(Path(__file__).resolve().parent / '_app_v14_base.py'), 'exec'), globals(), globals())
_patch_path = Path(__file__).resolve().parent / 'app_v14_patch.py'
_patch_source = _patch_path.read_text(encoding='utf-8')
exec(compile(_patch_source, str(_patch_path), 'exec'), globals(), globals())
