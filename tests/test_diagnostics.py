"""Synthetic-only explainability, counts, privacy and multigraph regressions."""
import copy
import json
import unittest
from unittest.mock import patch

from workflow_doctor.scanner import scan_uploads
from workflow_doctor.catalog import RULE_CATALOG
from workflow_doctor.reporting import report_view, render_report
from workflow_doctor.api.models import DiagnosticRecord


def node(kind='noOp', **values):
    return dict(id='n',name='node',type='n8n-nodes-base.'+kind,typeVersion=1,position=[0,0],parameters={},**values)


def workflow(identifier='A', target=None):
    n=node('executeWorkflow') if target else node()
    if target: n.update(typeVersion=1.2,parameters={'workflowId':target})
    return dict(id=identifier,name='FABRICATED',nodes=[n],connections={},settings={})


def scan(*items):
    return scan_uploads([(f'upload[{i}].json',json.dumps(w).encode()) for i,w in enumerate(items)])


class DiagnosticTests(unittest.TestCase):
    def test_catalog_has_all_current_rules_and_complete_documentation(self):
        self.assertEqual(len(RULE_CATALOG),15)
        for r in RULE_CATALOG.values():
            for key in ('rule_name','rule_category','trigger_condition','detection_scope','severity_default','limitations','remediation_guidance'):
                self.assertTrue(r[key])

    def test_scopes_category_and_distinct_dimensions(self):
        a=workflow('A','B'); a['settings']['errorWorkflow']='B'
        a['nodes'][0]['credentials']={'fabricated':{'id':'C'}}
        a['nodes'][0]['parameters']['path']='/fabricated/file.txt'
        checks=scan(a,workflow('B'))['analysis']['checks']
        by={f['rule_id']:f for f in checks}
        self.assertEqual(by['WF010']['scope'],'node')
        self.assertEqual(by['WF010']['category'],'credentials')
        self.assertEqual(by['WF013']['scope'],'node')
        self.assertEqual(by['WF013']['category'],'filesystem')
        self.assertEqual(by['WF009']['scope'],'workflow')
        self.assertEqual(by['WF016']['scope'],'environment')
        self.assertEqual(by['WF008']['diagnostic_status'],'pass')
        self.assertEqual(by['WF016']['confidence'],'high')
        self.assertEqual(by['WF016']['assessment'],'unknown')
        for f in checks: DiagnosticRecord.model_validate(f)

    def test_connection_scope_and_redacted_endpoints(self):
        w=workflow(); w['connections']={'node':{'main':[[{'node':'MISSING','type':'main','index':0}]]}}
        f=next(f for f in scan(w)['analysis']['checks'] if f['rule_id']=='WF005')
        self.assertEqual(f['scope'],'connection');self.assertTrue(f['connection_source']);self.assertTrue(f['connection_target'])
        self.assertNotIn('MISSING',json.dumps(f))

    def test_missing_id_and_duplicate_names_have_disambiguated_locators(self):
        w=workflow(); del w['nodes'][0]['id']; w['nodes'].append(node())
        checks=scan(w)['analysis']['checks']
        node_checks=[f for f in checks if f['scope']=='node']
        self.assertEqual({f['node_index'] for f in node_checks},{0,1})
        self.assertEqual(len({f['node_id'] for f in node_checks}),2)
        self.assertTrue(all(f['node_label'] for f in node_checks))
        excluded=scan(w,copy.deepcopy(w))['analysis']['checks']
        self.assertEqual(len({f['workflow_label'] for f in excluded}),2)

    def test_invalid_node_types_do_not_crash_projection(self):
        for value in ({},[],None):
            w=workflow();w['nodes'][0]['type']=value
            report=scan(w);self.assertTrue(report['analysis']['checks'])

    def test_ids_are_stable_unique_and_not_rule_ids(self):
        w=workflow();w['nodes'][0]['parameters']={'one':'/first','two':'/second'}
        a=scan(w); b=scan(w)
        rows=a['analysis']['checks']
        self.assertEqual([f['finding_id'] for f in rows],[f['finding_id'] for f in b['analysis']['checks']])
        paths=[f for f in rows if f['rule_id']=='WF013']
        self.assertEqual(len(paths),2);self.assertNotEqual(paths[0]['finding_id'],paths[1]['finding_id'])
        self.assertTrue(all(f['finding_id'].startswith('FND-') for f in rows))

    def test_statistics_reconcile_without_deduplicating_rule_hits(self):
        a=workflow('A','B');a['nodes'][0]['parameters']['extra']='/one'
        b=workflow('B','A')
        report=scan(a,b);analysis=report['analysis'];s=analysis['diagnostics']['statistics']
        self.assertEqual(s['check_count'],sum(s['assessment_counts'].values()))
        self.assertEqual(s['check_count'],len(analysis['checks']))
        self.assertEqual(s['finding_count'],sum(s['assessment_counts'][a] for a in ('blocked','risk','unknown')))
        self.assertLess(s['triggered_rule_count'],s['finding_count'])
        self.assertTrue(analysis['graphs']['workflow_dependencies']['has_cycles'])
        self.assertFalse(any(f['assessment']=='blocked' for f in analysis['checks']))

    def test_unresolved_targets_reconcile_and_dynamic_stays_separate(self):
        a=workflow('A','MISSING');b=workflow('B','MISSING');c=workflow('C','={{ $json.id }}')
        r=scan(a,b,c)['analysis'];d=r['diagnostics'];s=d['statistics']
        self.assertEqual(s['unresolved_reference_count'],2);self.assertEqual(s['unresolved_target_count'],1)
        self.assertEqual(s['dynamic_dependency_count'],1)
        g=r['graphs']['workflow_dependencies'];self.assertEqual(len(g['nodes']),4);self.assertEqual(len(g['edges']),2)
        for n in g['nodes']:
            if n.get('import_status')!='Included': self.assertTrue(n['dependency_ids'])
        self.assertTrue(d['dynamic_dependencies'][0]['target_workflow_id'] is None)

    def test_unknown_and_not_applicable_have_honest_explanations(self):
        r=scan(workflow('A','={{ $json.id }}'))
        for f in r['analysis']['checks']:
            if f['assessment']=='unknown':
                self.assertTrue(f['unknown_reason']);self.assertTrue(f['required_evidence']);self.assertTrue(f['recommended_verification'])
        self.assertTrue(any(f['assessment']=='not_applicable' for f in r['analysis']['checks']))

    def test_parallel_calls_preserve_evidence_and_counts(self):
        w=workflow('A','B');other=copy.deepcopy(w['nodes'][0]);other.update(id='second',name='second');w['nodes'].append(other)
        a=scan(w,workflow('B'))['analysis'];self.assertEqual(len(a['graphs']['workflow_dependencies']['edges']),2)
        self.assertEqual(len([f for f in a['checks'] if f['rule_id']=='WF008']),2)

    def test_secret_unicode_and_source_never_leak_or_change(self):
        w=workflow();marker='FABRICATED_PRIVATE_VALUE'
        w['name']=marker;w['nodes'][0]['name']=marker;w['nodes'][0]['id']=marker
        w['nodes'][0]['parameters']={'Authorization':marker,'Cookie':marker,'path':'/private/'+marker}
        before=copy.deepcopy(w)
        with patch('pathlib.Path.open',side_effect=AssertionError('no input filesystem access')):
            report=scan(w)
        for fmt in ('json','text','markdown','html'):
            text=render_report(report,fmt);self.assertNotIn(marker,text);self.assertIn('WF013',text)
        self.assertEqual(w,before)

    def test_report_parity_for_ids_paths_and_localization(self):
        r=scan(workflow('A','MISSING'));view=report_view(r)
        for fmt in ('json','text','markdown','html'):
            text=render_report(r,fmt)
            for f in view['issues']:
                self.assertIn(f['finding_id'],text)
            self.assertIn('WF008',text)
        self.assertEqual(len(view['issues']),r['analysis']['diagnostics']['statistics']['check_count'])

    def test_real_api_envelope_validates_and_matches_canonical_report(self):
        from fastapi.testclient import TestClient
        from workflow_doctor.api.app import create_app
        with TestClient(create_app(),base_url='http://127.0.0.1') as client:
            response=client.post('/api/v1/scans',files={'files':('synthetic.json',json.dumps(workflow('A','MISSING')).encode(),'application/json')})
            self.assertEqual(response.status_code,200)
            envelope=response.json()
            self.assertEqual(envelope['diagnostic_records'],envelope['findings'])
            canonical=client.get('/api/v1/scans/'+envelope['scan_id']+'/report').json()
            self.assertEqual(envelope['diagnostics']['statistics'],canonical['analysis']['diagnostics']['statistics'])

    def test_unknown_versions_are_not_counted_as_dynamic_expressions(self):
        w=workflow('A','B');w['nodes'][0]['typeVersion']=999
        d=scan(w)['analysis']['diagnostics']
        self.assertEqual(d['statistics']['dynamic_dependency_count'],0)
        self.assertEqual(len(d['unknown_workflow_dependencies']),1)

    def test_malicious_keys_and_unicode_stay_out_of_evidence(self):
        marker='FABRICATED_PRIVATE_HEADER\u202e<script>'
        w=workflow();w['nodes'][0]['parameters']={marker:'/fabricated/file'}
        for format in ('text','markdown','html'):
            output=render_report(scan(w),format)
            self.assertNotIn(marker,output)
            self.assertNotIn('<script>',output)


if __name__=='__main__':unittest.main()
