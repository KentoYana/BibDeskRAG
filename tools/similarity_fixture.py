"""Standard-library-only synthetic saved vectors for installed-package/SDK checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import subprocess


def create_saved_fixture(command: list[str], root: Path, environment: dict):
    root = root.resolve()
    root.mkdir(parents=True)
    env = environment.copy()
    env['BIBDESK_RAG_HOME'] = str(root / 'app-home')
    env.pop('BIBDESK_RAG_CONFIG', None)
    bib, config, database = root/'refs.bib', root/'config.toml', root/'derived/index.sqlite3'
    bib.write_text('''@article{SavedSeed,title={Generated repair seed},abstract={Generated seed abstract}}
@article{SavedRelated,title={Generated related candidate},year={2026},author={Fixture, Alice}}
@article{SavedOther,title={Generated other topic},abstract={Generated background},year={2025}}
@article{SavedMissing,title={Generated missing vectors}}
''' + '\n'.join('@article{ZBackground'+str(i)+',title={Background '+str(i)+'}}' for i in range(12))+'\n@article{SavedUnrelatedControl,title={Zyqorp}}\n')
    def run(*args):
        return subprocess.run([*command, *args], env=env, text=True, capture_output=True,
                              check=True, timeout=60).stdout
    run('--config', 'create', str(config), '--bib', str(bib), '--data-dir', str(root/'derived'))
    run('--temp', str(config), '--index', 'update')
    config.write_text(config.read_text() + '\n[semantic]\nenabled = true\ndimensions = 384\n')
    settings = json.loads(run('--temp', str(config), '--config', 'show', '--format', 'json'))['semantic']
    info = {k: settings[k] for k in ('model', 'revision', 'dimensions', 'passage_prefix', 'query_prefix', 'max_tokens')}
    info.update(backend='sentence-transformers/generated-fixture-not-real-inference',
                preprocessing='unicode-fields-whitespace-nfc-v1;character-split-v1;title-anchor-v2')
    with sqlite3.connect(database) as db:
        model = db.execute('INSERT INTO embedding_models(name,version,dimensions,config_json) VALUES (?,?,?,?)',
                          (info['model'], info['revision'], 384, json.dumps(info, sort_keys=True))).lastrowid
        vectors = {'SavedSeed': (1.,0.,0.,0.), 'SavedRelated': (1.,0.,0.,0.),
                   'SavedOther': (0.,1.,0.,0.), 'SavedUnrelatedControl': (0.,0.,1.,0.)}
        vectors.update({f'ZBackground{i}':(0.,1.,0.,0.) for i in range(12)})
        for key, vector in vectors.items():
            paper = db.execute('SELECT id,title,abstract FROM papers WHERE citekey=?', (key,)).fetchone()
            digest = hashlib.sha256(json.dumps(paper[1:], ensure_ascii=False).encode()).hexdigest()
            db.execute('INSERT INTO embeddings(paper_id,part,model_id,content_hash,vector,embedded_at,title_only) VALUES (?,?,?,?,?,?,?)',
                       (paper[0], 0, model, digest, struct.pack('<384f', *vector, *([0.]*380)), 'generated fixture', not bool(paper[2])))
        db.execute("INSERT INTO settings VALUES ('semantic_model_id',?)", (str(model),))
    assert not Path(settings['cache_dir']).exists()
    return config, database, env
