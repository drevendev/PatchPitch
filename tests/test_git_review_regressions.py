"""Review regressions: original checkpoints, editable facts and save limits."""
import copy
import json

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from patchpitch import generator, git_import, sessions
from patchpitch.app import app
from test_browser import ui_url
from test_git_import import git_repository, large_git_repository


@pytest.fixture
def partial_git_session(large_git_repository, monkeypatch):
    root, base, head = large_git_repository
    def model(path, payload, timeout):
        ids = payload['format']['$defs']['Candidate']['properties']['evidence_ids']['items']['enum']
        return {'done': True, 'model': 'MOCK', 'message': {'content': json.dumps({'facts': [
            {'text': 'Committed values were added.', 'kind': 'implemented', 'evidence_ids': [ids[0]]}]})}}
    monkeypatch.setattr(generator, 'ollama_json', model)
    picked = git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=['feature.py'])
    preview = git_import.preview(picked)
    response = git_import.extract(git_import.ExtractInput(**picked.model_dump(), reviewed=True,
        preview_sha256=preview['preview_sha256']))
    run = {'schema_version': 2, 'kind': 'patchpitch_git_review', 'status': 'partial', **copy.deepcopy(preview),
        'attempts': [{'batch_index': 0, 'status': 'accepted', 'response': response, 'error': None},
            {'batch_index': 1, 'status': 'failed', 'response': {'raw_response': {'message': {'content': 'Rejected original'}}},
             'error': {'code': 'invalid_draft', 'message': 'Rejected batch'}}]}
    review = {'inspection': git_import.inspect(git_import.InspectInput(repo_path=str(root), count=1)),
        'preview': preview, 'facts': [{**f, 'batch_index': 0, 'current_text': 'Keep this exact reviewed text.\n', 'include': True}
            for f in response['facts']], 'record': run, 'selected_files': ['feature.py']}
    return {'kind': 'patchpitch_session', 'schema_version': 1,
        'form': {'product': '', 'description': '', 'audience': '', 'release': '', 'voice': '', 'cta': '',
            'changes': '', 'media_note': '', 'format': 'devlog', 'style': 'warm', 'intent': 'show_result',
            'post_count': 5, 'auto_tags': False, 'writing_goal': 'development'},
        'changes': [], 'preview_text': None, 'pack_context': None, 'drafts': [], 'active_key': None,
        'records': [], 'record_choice': None, 'publication_markers': {}, 'git_record': None,
        'git_controls': {'git-repo': str(root), 'git-mode': 'recent', 'git-count': '1',
            'git-base': '', 'git-head': 'HEAD', 'git-path': ''}, 'git_review': review}


def large_history(saved):
    run = saved['git_review']['record']
    failure = copy.deepcopy(run['attempts'][1])
    failure['response']['raw_response']['message']['content'] = 'Rejected original: ' + 'x'*60_000
    run['attempts'] = [run['attempts'][0], *[copy.deepcopy(failure) for _ in range(80)]]
    return saved


def test_large_checkpoint_history_round_trips_through_api(partial_git_session):
    saved = large_history(partial_git_session)
    assert len(json.dumps(saved).encode()) > 4_000_000
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.post('/api/session/validate', json=saved)
    assert response.status_code == 200
    assert response.json() == saved


@pytest.mark.parametrize('change_original', [False, True], ids=['manual-edit', 'altered-original'])
def test_invalidated_preview_retains_validated_candidate_edits(partial_git_session, change_original):
    review = partial_git_session['git_review']
    cached = copy.deepcopy(review['facts'])
    cached[0]['current_text'] = 'Another exact manual edit.\n'
    if change_original:
        cached[0]['text'] = 'Altered original'
    review['record']['candidate_edits'] = cached
    review.update(preview=None, facts=None, selected_files=[])
    if change_original:
        with pytest.raises(ValueError): sessions.validate_file(partial_git_session)
    else:
        assert sessions.validate_file(partial_git_session)['git_review']['record']['candidate_edits'] == cached


def test_reinspect_save_open_reattaches_edits_and_continues_only_remaining_batches(ui_url, partial_git_session, tmp_path):
    saved = partial_git_session
    path = tmp_path/'partial.json'
    path.write_text(json.dumps(saved), encoding='utf-8')
    requests = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = browser.new_page()
        page.on('dialog', lambda d: d.accept())
        page.route('**/api/health', lambda r: r.fulfill(json={'ollama': 'ready', 'model': 'MOCK'}))
        def extract(route):
            body = route.request.post_data_json; requests.append(body['batch_index'])
            route.fulfill(json=git_import.extract(git_import.ExtractInput.model_validate(body)))
        page.route('**/api/git/facts', extract)
        page.goto(ui_url); page.locator('#open-session').set_input_files(path)
        page.locator('#git-tools > summary').click()
        expect(page.get_by_role('textbox', name='Review fact 1', exact=True)).to_have_value('Keep this exact reviewed text.\n')
        page.locator('#git-inspect').click()
        expect(page.locator('#git-reviewed')).to_be_disabled()
        page.locator('#session-tools > summary').click()
        with page.expect_download() as event: page.locator('#save-session').click()
        invalidated = tmp_path/'invalidated.json'; event.value.save_as(invalidated)
        snapshot = json.loads(invalidated.read_text(encoding='utf-8'))
        assert snapshot['git_review']['record']['candidate_edits'] == saved['git_review']['facts']
        page.reload(); page.locator('#open-session').set_input_files(invalidated)
        page.locator('#git-tools > summary').click()
        page.get_by_role('checkbox', name='Use file feature.py', exact=True).check()
        page.locator('#git-preview').click()
        expect(page.locator('#git-reviewed')).to_be_enabled(timeout=30000)
        expect(page.get_by_role('textbox', name='Review fact 1', exact=True)).to_have_value('Keep this exact reviewed text.\n')
        expect(page.get_by_role('checkbox', name='Use fact 1', exact=True)).to_be_checked()
        page.locator('#git-reviewed').check(); page.locator('#git-extract').click()
        expect(page.locator('#git-progress')).to_contain_text(' · complete ·', timeout=60000)
        assert requests == list(range(1, len(saved['git_review']['preview']['chunking']['batches'])))
        expect(page.get_by_role('textbox', name='Review fact 1', exact=True)).to_have_value('Keep this exact reviewed text.\n')
        browser.close()


def test_browser_opens_and_saves_history_larger_than_four_mb(ui_url, partial_git_session, tmp_path):
    saved = large_history(partial_git_session)
    path = tmp_path/'large.json'; path.write_text(json.dumps(saved), encoding='utf-8')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = browser.new_page()
        page.route('**/api/health', lambda r: r.fulfill(json={'ollama': 'ready', 'model': 'MOCK'}))
        page.goto(ui_url); page.locator('#open-session').set_input_files(path)
        expect(page.locator('#status')).to_contain_text('Session opened')
        page.locator('#session-tools > summary').click()
        with page.expect_download() as event: page.locator('#save-session').click()
        exported = tmp_path/'exported.json'; event.value.save_as(exported)
        assert exported.stat().st_size > 4_000_000
        actual = json.loads(exported.read_text(encoding='utf-8'))
        assert actual['git_review'] == saved['git_review']
        page.reload(); page.locator('#open-session').set_input_files(exported)
        expect(page.locator('#status')).to_contain_text('Session opened')
        browser.close()


def test_pretty_download_limit_is_checked_before_sending_or_losing_work(ui_url, partial_git_session, tmp_path):
    path = tmp_path/'small.json'; path.write_text(json.dumps(partial_git_session), encoding='utf-8')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = browser.new_page()
        page.route('**/api/health', lambda r: r.fulfill(json={'ollama': 'ready', 'model': 'MOCK'}))
        page.goto(ui_url); page.locator('#open-session').set_input_files(path)
        expect(page.locator('#status')).to_contain_text('Session opened')
        # Each original failed response is <128 KB. Pretty-printing the retained
        # arrays can still exceed the file budget although compact JSON fits.
        sizes = page.evaluate('''() => {
          const run=gitState.record, failure=structuredClone(run.attempts[1]);
          failure.response.raw_response.context=Array(24000).fill(0);
          run.attempts=[run.attempts[0], ...Array.from({length:80},()=>structuredClone(failure))];
          const saved=sessionSnapshot();
          return {compact:new TextEncoder().encode(JSON.stringify(saved)).length,
                  pretty:new TextEncoder().encode(JSON.stringify(saved,null,2)+"\\n").length};
        }''')
        assert sizes['compact'] < 32_000_000 < sizes['pretty']
        requests, downloads = [], []
        page.on('request', lambda r: requests.append(r.url) if r.url.endswith('/api/session/validate') else None)
        page.on('download', lambda download: downloads.append(download))
        page.locator('#session-tools > summary').click(); page.locator('#save-session').click()
        expect(page.locator('#error')).to_contain_text('32 MB')
        assert not requests and not downloads
        assert page.evaluate('gitState.record.attempts.length') == 81
        assert page.evaluate('gitState.facts[0].current_text') == 'Keep this exact reviewed text.\n'
        browser.close()
