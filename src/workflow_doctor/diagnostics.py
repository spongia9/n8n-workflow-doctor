"""Canonical additive diagnostic projection. Pure, bounded by scanner budgets."""
import json
import re
from collections import defaultdict

from .catalog import RULE_CATALOG, STATUS_ZH, SCOPE_ZH, RESOLUTION_ZH, KINDS_ZH, MESSAGE_ZH
from .privacy import fingerprint

_PATH = re.compile(r'^\$\.nodes\[(\d+)\]')
SAFE_TYPES = {'n8n-nodes-base.' + v for v in ('manualTrigger','noOp','executeWorkflow','httpRequest','webhook',
              'if','switch','readWriteFile','readBinaryFile','writeBinaryFile','errorTrigger','code','set')}
SAFE_TYPES.add('@n8n/n8n-nodes-langchain.agent')


def identities(documents):
    """Retain locators, never restore arbitrary names/IDs which may contain secrets."""
    output = {}
    for source, data in documents:
        if not isinstance(data, dict):
            continue
        wf = fingerprint('workflow-content', json.dumps(data, sort_keys=True, ensure_ascii=True))
        nodes = []
        for index, node in enumerate(data.get('nodes', []) if isinstance(data.get('nodes'), list) else []):
            if not isinstance(node, dict):
                continue
            raw_id = node.get('id')
            key = fingerprint('node', raw_id) if isinstance(raw_id, str) and raw_id else fingerprint('node-position', wf + ':' + str(index))
            nodes.append({'node_id': key, 'node_index': index, 'node_name': None,
                          'node_label': f'节点 {index + 1} · {key[-8:]}',
                          'node_type': node.get('type') if isinstance(node.get('type'),str) and node.get('type') in SAFE_TYPES else None,
                          'node_type_fingerprint': fingerprint('node-type', str(node.get('type'))),
                          'identity_kind': 'node_id_fingerprint' if isinstance(raw_id,str) and raw_id else 'temporary_node_position',
                          'name_fingerprint': fingerprint('node-name', str(node.get('name')))})
        links={}
        by_name={}
        raw_nodes=data.get('nodes', []) if isinstance(data.get('nodes'),list) else []
        for n in nodes:
            name=raw_nodes[n['node_index']].get('name')
            if isinstance(name,str): by_name.setdefault(name,[]).append(n['node_id'])
        connections=data.get('connections',{})
        if isinstance(connections,dict):
            for si,(name,types) in enumerate(connections.items()):
                loc=f'$.connections{{source:{si}}}'
                source_id=by_name.get(name,[])
                safe_source=source_id[0] if len(source_id)==1 else fingerprint('node-name-reference',str(name))
                links[loc]={'connection_source':safe_source,'connection_target':None}
                if not isinstance(types,dict): continue
                for ti,ports in enumerate(types.values()):
                    if not isinstance(ports,list): continue
                    for oi,items in enumerate(ports):
                        if not isinstance(items,list): continue
                        for li,link in enumerate(items):
                            target=link.get('node') if isinstance(link,dict) else None
                            targets=by_name.get(target,[]) if isinstance(target,str) else []
                            links[f'{loc}{{type:{ti}}}[{oi}][{li}]']={'connection_source':safe_source,
                                'connection_target':targets[0] if len(targets)==1 else fingerprint('node-name-reference',str(target)) if target is not None else None}
        output[source] = {'workflow_fingerprint': wf, 'workflow_name': None, 'nodes': nodes, 'connections':links,
                          'name_fingerprint': fingerprint('workflow-name', str(data.get('name'))),
                          'identity_notice': '名称和原始 ID 默认脱敏；使用证据位置和指纹在原文件本地定位。'}
    return output


def decorate(check, identity=None):
    """Add fields to a copy; legacy enum/diagnostic text stays intact."""
    f = dict(check)
    rule = RULE_CATALOG.get(f['rule_id'],{'rule_name':'未登记的规则说明','rule_category':'unknown',
        'detection_scope':'workflow','remediation_guidance':'按原始规则与证据进行人工核查。'})
    path = f['evidence_location']
    identity = identity or {}
    match = _PATH.match(path)
    index = int(match[1]) if match else None
    node = next((n for n in identity.get('nodes', []) if n['node_index'] == index), {})
    scope = 'connection' if path.startswith('$.connections') else 'node' if index is not None else rule['detection_scope']
    if scope == 'node' and not node and f.get('node_id') is None:
        scope = 'workflow'
    content = identity.get('workflow_fingerprint') or fingerprint('file', f.get('file', ''))
    basis = [f['rule_id'], content, f.get('file'), node.get('node_id', f.get('node_id')), path, f['assessment'], f.get('dependency_ids', [])]
    f.update(finding_id='FND-' + fingerprint('finding', json.dumps(basis, sort_keys=True))[-24:],
             workflow_name=None, workflow_label=identity.get('workflow_label') or '输入文件 · '+fingerprint('file',f.get('file',''))[-8:],
             workflow_source_file=f.get('file'), workflow_fingerprint=content,
             scope=scope, category=rule['rule_category'], node_name=None,
             node_index=index, node_label=node.get('node_label'), node_type=node.get('node_type'),
             connection_source=None, connection_target=None, parameter_path=path, evidence=path,
             rule_name=rule['rule_name'], message_zh=MESSAGE_ZH.get(f['message'],rule['rule_name']), recommendation_zh=rule['remediation_guidance'],
             status_zh=STATUS_ZH[f['assessment']], scope_zh=SCOPE_ZH[scope],
             severity_level={'error':'high','warning':'medium','info':'low'}.get(f['severity'], 'low'),
             diagnostic_status={'verified':'pass','blocked':'blocker'}.get(f['assessment'], f['assessment']),
             unknown_reason=None, required_evidence=[], recommended_verification=[],
             identity_notice=identity.get('identity_notice','原始身份未提供；不推测名称。'))
    if node:
        f['node_id'] = node['node_id']
    if f['assessment']=='not_applicable':
        f['message_zh']='未配置显式错误工作流；该引用的迁移映射不适用。'
        f['recommendation_zh']='本项无需映射外部错误工作流；其他运行和环境检查仍需核查。'
    elif f['assessment']=='verified':
        f['message_zh']=rule['rule_name']+'：仅确认当前导入集合的静态匹配，未验证目标环境。'
    connection_match=re.match(r'(\$\.connections\{source:\d+\})(?:\{type:\d+\}\[\d+\]\[\d+\])?',path)
    if connection_match:
        links=identity.get('connections',{})
        connection=links.get(connection_match[0]) or links.get(connection_match[1])
        if connection: f.update(connection)
    if f['assessment'] == 'unknown':
        if f['rule_id'] == 'WF016':
            reason='没有提供目标环境版本、权限或资源的核查证据。'
            required=['经授权核查的目标 n8n/节点版本、权限和资源信息']
        elif f['rule_id'] in ('WF008','WF009'):
            reason='动态表达式、未知版本或不支持的调用形式，无法从静态 JSON 确定目标。'
            required=['原文件中调用节点的表达式和参数结构（本地检查）', '实际解析的目标工作流与版本信息']
        else:
            reason='提取器无法确认动态值或目标环境能力；这不代表工作流存在错误。'
            required=['原文件中相应节点的参数结构（本地检查）', '目标资源/节点版本及权限证据']
        f.update(unknown_reason=reason, required_evidence=required,
                 recommended_verification=['在本地按证据路径检查原始配置，不运行导入代码。','在获授权的目标环境人工核查，不向报告提供秘密值。'])
    return f


def statistics(findings, graph, dependencies, workflow_count, node_count, connection_count):
    states={k:sum(f['assessment']==k for f in findings) for k in STATUS_ZH}
    cross=[d for d in dependencies if d['kind'] in ('sub_workflow','error_workflow')]
    unresolved=[d for d in cross if d['target_workflow_id'] and d['status'] != 'Found In Import Set']
    dynamic=[d for d in cross if d['status']=='Unknown' and 'dynamic' in d.get('reference_form','')]
    problems=[f for f in findings if f['assessment'] in ('blocked','risk','unknown')]
    return dict(workflow_count=workflow_count, internal_node_count=node_count, internal_connection_count=connection_count,
                check_count=len(findings), finding_count=len(problems), record_count=len(findings),
                triggered_rule_count=len({f['rule_id'] for f in problems}), risk_finding_count=states['risk'],
                blocker_count=states['blocked'], unknown_count=states['unknown'], not_applicable_count=states['not_applicable'],
                assessment_counts=states, graph_node_count=len(graph.get('nodes',[])), graph_edge_count=len(graph.get('edges',[])),
                unresolved_reference_count=len(unresolved), unresolved_target_count=len({d['target_workflow_id'] for d in unresolved}),
                dynamic_dependency_count=len(dynamic))


def enrich(analysis, documents):
    import networkx as nx
    from .graphs import graph_from_json, upstream, downstream
    meta=identities(documents)
    for i,w in enumerate(analysis['workflows']):
        m=meta[w['file']]; m['workflow_label']=f'工作流 {i+1}'
        w.update({k:v for k,v in m.items() if k not in ('nodes','connections')})
        w['node_count']=len(m['nodes'])
    analysis['identities']=meta
    analysis['checks']=[decorate(f,meta.get(f['file'])) for f in analysis['checks']]
    deps=analysis['dependencies']; by_id={d['id']:d for d in deps}
    for f in analysis['checks']:
        linked=[by_id[i] for i in f.get('dependency_ids',[]) if i in by_id]
        if linked and linked[0]['status']=='Missing From Import Set':
            f['message_zh'] += '：本次导入集合未包含目标，不能判断目标实例是否存在。'
    graph=analysis['graphs']['workflow_dependencies']
    workflows={w['workflow_id']:w for w in analysis['workflows']}
    g=graph_from_json(graph)
    condensation=nx.condensation(g)
    positions={}
    for level,generation in enumerate(nx.topological_generations(condensation)):
        row=0
        for component in sorted(generation):
            for node in sorted(condensation.nodes[component]['members']):
                positions[node]={'x':level*360,'y':row*210}; row+=1
    query={}
    dependency_ids=defaultdict(list)
    checks_by_workflow=defaultdict(list)
    for d in deps:
        dependency_ids[d['workflow_id']].append(d['id'])
        if d['target_workflow_id'] and d['target_workflow_id']!=d['workflow_id']:
            dependency_ids[d['target_workflow_id']].append(d['id'])
    for f in analysis['checks']: checks_by_workflow[f['workflow_id']].append(f)
    cycle_groups={key:i+1 for i,c in enumerate(graph['cyclic_components']) for key in c}
    for n in graph['nodes']:
        n.update(workflows.get(n['id'],{}))
        n['dependency_ids']=dependency_ids[n['id']]
        n['position']=positions.get(n['id'],{'x':0,'y':0})
        n['finding_ids']=[f['finding_id'] for f in checks_by_workflow[n['id']]]
        n['finding_count']=len(n['finding_ids'])
        n['cycle_group']=cycle_groups.get(n['id'])
        n['risk_count']=sum(f['assessment'] in ('risk','blocked') for f in checks_by_workflow[n['id']])
        query[n['id']]={'upstream':upstream(g,n['id']), 'downstream':downstream(g,n['id'])}
    for ng in analysis['graphs']['node_graphs']:
        indexed_nodes={n['node_index']:n for n in meta[ng['file']]['nodes']}
        cycles={key:i+1 for i,c in enumerate(ng['cyclic_components']) for key in c}
        internal=graph_from_json(ng)
        condensed=nx.condensation(internal)
        internal_positions={}
        for level,generation in enumerate(nx.topological_generations(condensed)):
            row=0
            for component in sorted(generation):
                for key in sorted(condensed.nodes[component]['members']):
                    internal_positions[key]={'x':level*360,'y':row*210};row+=1
        for n in ng['nodes']:
            node=indexed_nodes.get(n['node_index'],{})
            n.update(node)
            n['position']=internal_positions[n['id']]
            n['cycle_group']=cycles.get(n['id'])
    for d in deps:
        identity=meta.get(d['file'],{})
        match=_PATH.match(d['evidence_location']); idx=int(match[1]) if match else None
        node=next((v for v in identity.get('nodes',[]) if v['node_index']==idx),{})
        d.update(source_node_index=idx, source_node_label=node.get('node_label'), source_workflow_label=identity.get('workflow_label'),
                 status_zh=RESOLUTION_ZH.get(d['status'],'需要人工核查'), kind_zh=KINDS_ZH.get(d['kind'],'其他依赖'))
    summary=statistics(analysis['checks'],graph,deps,len(analysis['workflows']),analysis['summary']['node_count'],analysis['summary']['connection_count'])
    analysis['diagnostics']={'statistics':summary,'rules':list(RULE_CATALOG.values()),'graph_queries':query,
        'unresolved_dependencies':[d for d in deps if d['kind'] in ('sub_workflow','error_workflow') and d['target_workflow_id'] and d['status']!='Found In Import Set'],
        'dynamic_dependencies':[d for d in deps if d['kind'] in ('sub_workflow','error_workflow') and d['status']=='Unknown' and 'dynamic' in d['reference_form']],
        'unknown_workflow_dependencies':[d for d in deps if d['kind'] in ('sub_workflow','error_workflow') and d['status']=='Unknown'],
        'notice':'检查总数包含通过与不适用；Finding 总数仅计阻断、风险及未知。全部统计为未筛选的导入集合。'}
    return analysis
