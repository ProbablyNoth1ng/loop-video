import json
import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from cloud import install


class VisionInstallTests(unittest.TestCase):
    def test_complete_legacy_cache_migrates_without_resolving_or_replacing_weights(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':self.hub([])}):
            root=Path(tmp);comfy=root/'ComfyUI';(comfy/'models').mkdir(parents=True);state=root/'state';state.mkdir()
            assets=[dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                         target='renderer.safetensors',local_dir='.')]
            records=[]
            for target,repo in [('renderer.safetensors','Org/Renderer'),
                ('Qwen3-VL-8B-Instruct/config.json','Qwen/Qwen3-VL-8B-Instruct'),
                ('Qwen3-VL-8B-Instruct/model.safetensors','Qwen/Qwen3-VL-8B-Instruct'),
                (install.UPSCALER,None)]:
                path=comfy/'models'/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'kept')
                record=dict(target=target,size=4,sha256=install.sha256(path))
                if repo:record.update(repo=repo,revision='b'*40,filename=path.name,
                                      local_dir=str(Path(target).parent).replace('\\','/'))
                records.append(record)
            signature=hashlib.sha256(json.dumps(assets,sort_keys=True).encode()).hexdigest()
            install.write_json(state/'models-ready.json',dict(signature=signature,files=records))
            with patch.object(install,'model_assets',return_value=assets),patch.object(install,'resolve_plan',side_effect=AssertionError('must keep pinned revision')):
                install.download_models(root,comfy,state)
            ready=install.read_json(state/'models-ready.json')
            self.assertEqual(ready['vision_repo'],'Qwen/Qwen3-VL-8B-Instruct')
            self.assertEqual(ready['files'],records)
            self.assertEqual((comfy/'models/Qwen3-VL-8B-Instruct/model.safetensors').read_bytes(),b'kept')

    def test_new_workflow_matches_installed_analyzer_and_saved_workflows_are_preserved(self):
        project=Path(__file__).resolve().parents[1]
        for repo,path,mode in [('Qwen/Qwen3.5-9B','models/Qwen3.5-9B','local Qwen3.5'),
                               ('Qwen/Qwen3-VL-8B-Instruct','models/Qwen3-VL-8B-Instruct','local Qwen')]:
            with tempfile.TemporaryDirectory() as tmp:
                destination=Path(tmp)
                install.install_workflows(project,destination,repo)
                workflow=json.loads((destination/'ambient-motion.json').read_text())
                editor=next(n for n in workflow['nodes'] if n['type']=='AmbientMotionEditor')
                self.assertEqual(editor['widgets_values'][7:9],[path,mode])
                self.assertEqual((destination/'ltx-2.5-motion-track.official.json').read_bytes(),
                                 (project/'workflows/ltx-2.5-motion-track.official.json').read_bytes())
                saved=destination/'ambient-motion.json';saved.write_text('{"custom":"saved widgets"}')
                install.install_workflows(project,destination,'Qwen/Qwen3.5-9B')
                self.assertEqual(saved.read_text(),'{"custom":"saved widgets"}')

    def hub(self, downloads):
        class Api:
            def model_info(self, repo, revision, files_metadata):
                names = ['config.json','model.safetensors'] if repo.startswith('Qwen/') else ['renderer.safetensors']
                return types.SimpleNamespace(sha='a'*40,siblings=[types.SimpleNamespace(
                    rfilename=name,size=4,lfs=None) for name in names])
        def download(repo_id, filename, revision, local_dir):
            self.assertEqual(revision,'a'*40)
            downloads.append((repo_id,filename))
            path = Path(local_dir)/filename;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'data');return str(path)
        return types.SimpleNamespace(HfApi=Api,hf_hub_download=download)

    def test_both_snapshots_have_distinct_destinations_and_immutable_revisions(self):
        with patch.dict(sys.modules, {'huggingface_hub':self.hub([])}):
            for repo, folder in [('Qwen/Qwen3.5-9B','Qwen3.5-9B'),
                                 ('Qwen/Qwen3-VL-8B-Instruct','Qwen3-VL-8B-Instruct')]:
                records = install.resolve_plan([], vision_repo=repo)
                self.assertEqual({r['target'] for r in records},{folder+'/config.json',folder+'/model.safetensors'})
                self.assertTrue(all(r['revision']=='a'*40 for r in records))

    def test_selection_changes_cache_identity_preserves_old_weights_and_records_checksums(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'huggingface_hub':self.hub(calls)}):
            root=Path(tmp);comfy=root/'ComfyUI';comfy.mkdir();state=root/'state';state.mkdir()
            upscaler=comfy/'models'/install.UPSCALER;upscaler.parent.mkdir(parents=True);upscaler.write_bytes(b'anime')
            old=comfy/'models/Qwen3-VL-8B-Instruct/model.safetensors';old.parent.mkdir();old.write_bytes(b'old!')
            install.write_json(state/'models-ready.json', {'signature':'old',
                'vision_repo':'Qwen/Qwen3-VL-8B-Instruct', 'files':[{'target':install.UPSCALER,
                'size':5,'sha256':install.sha256(upscaler)}]})
            assets=[dict(repo='Org/Renderer',revision='main',filename='renderer.safetensors',
                         target='renderer.safetensors',local_dir='.')]
            with patch.object(install,'model_assets',return_value=assets),patch.object(install,'read_json',wraps=install.read_json) as read:
                # Only the workflow read is a fixture; manifests use real disk files.
                read.side_effect=lambda path: {} if path.name=='ltx-2.5-motion-track.official.json' else json.loads(path.read_text()) if path.is_file() else None
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                ready=install.read_json(state/'models-ready.json')
                self.assertEqual(ready['vision_repo'],'Qwen/Qwen3.5-9B')
                self.assertTrue(all(len(r['sha256'])==64 for r in ready['files']))
                first=ready['signature'];count=len(calls)
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                self.assertEqual(len(calls),count)
                self.assertEqual(old.read_bytes(),b'old!')
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3-VL-8B-Instruct')
                self.assertNotEqual(install.read_json(state/'models-ready.json')['signature'],first)
                self.assertTrue((comfy/'models/Qwen3.5-9B/model.safetensors').is_file())
                for folder in ('Qwen3.5-9B','Qwen3-VL-8B-Instruct'):
                    provenance=install.read_json(state/('vision-'+folder+'.json'))
                    self.assertTrue(all(r['revision']=='a'*40 and len(r['sha256'])==64 for r in provenance['files']))
                count=len(calls)
                install.download_models(root,comfy,state,vision_repo='Qwen/Qwen3.5-9B')
                self.assertEqual(len(calls),count)
                self.assertEqual(install.read_json(state/'models-ready.json')['vision_repo'],'Qwen/Qwen3.5-9B')

    def test_new_install_defaults_to_35_and_legacy_install_keeps_its_choice(self):
        self.assertEqual(install.select_vision_repo(None,None),'Qwen/Qwen3.5-9B')
        legacy={'files':[{'repo':'Qwen/Qwen3-VL-8B-Instruct'}]}
        self.assertEqual(install.select_vision_repo(None,legacy),'Qwen/Qwen3-VL-8B-Instruct')
        self.assertEqual(install.select_vision_repo('Qwen/Qwen3.5-9B',legacy),'Qwen/Qwen3.5-9B')
        with self.assertRaises(ValueError):
            install.select_vision_repo('../../outside',None)
