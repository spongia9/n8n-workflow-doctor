# n8n Workflow Doctor — Migration dependency report

Input: examples\\sprint2\\workflows

Batch complete: True; structural findings: 0; input errors: 0.


## Structural findings


## Summary

| Metric | Count |
| --- | --- |
| workflow\_count | 4 |
| excluded\_file\_count | 0 |
| node\_count | 12 |
| connection\_count | 6 |
| dependency\_count | 14 |
| static\_dependency\_count | 12 |
| unknown\_dependency\_count | 2 |
| missing\_resource\_count | 1 |
| risk\_count | 14 |
| manual\_review\_count | 15 |

Compatibility: **unknown**. IDs are stable fingerprints; temporary file IDs are explicitly marked.

## Workflow identities

| Workflow ID | Identity kind | File |
| --- | --- | --- |
| workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | n8n\_id\_fingerprint | examples\\sprint2\\workflows\\A.json |
| workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41 | n8n\_id\_fingerprint | examples\\sprint2\\workflows\\B.json |
| workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | n8n\_id\_fingerprint | examples\\sprint2\\workflows\\C.json |
| workflow:sha256:d14d26a907fe1c69f9b504a191bd038c719bc7f2528eb33d3d0ccc0da55d2119 | n8n\_id\_fingerprint | examples\\sprint2\\workflows\\ERROR\_HANDLER.json |

## Migration risks

### WF009 — Error Workflow reference requires migration review

- Severity: info; status: Found In Import Set; confidence: high.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: None.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.settings.errorWorkflow.
- Dependencies: dependency:0.
- Recommendation: Map the error workflow after import and verify its Error Trigger and permissions manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:cff1f7ecc7fe2249ca2ff0302419ab1e3ac86da70cbc90a0c6cffff0c9503b41.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[2\].parameters.workflowId.value.
- Dependencies: dependency:1.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:c8e2fddd68f2eedd2e5d1f934cf3dd2bd8591b25f69c7485e0c0ef2137c53b06.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[3\].parameters.workflowId.value.
- Dependencies: dependency:2.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF010 — Credential reference requires reconfiguration

- Severity: warning; status: Requires Reconfiguration; confidence: high.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:a628d4b63ffaefa30197033e6666bb03c933358fb1265684d1cbe94bd2dedd68.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[4\].credentials{member:0}.id.
- Dependencies: dependency:3.
- Recommendation: Recreate or securely map credentials on the destination; verify permissions without disclosing secrets.

### WF012 — Environment variable dependency requires review

- Severity: warning; status: Requires Review; confidence: medium.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:a628d4b63ffaefa30197033e6666bb03c933358fb1265684d1cbe94bd2dedd68.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[4\].parameters{member:2}.
- Dependencies: dependency:5.
- Recommendation: Provision the required environment variable and check access policy; never copy its value into the report.

### WF012 — n8n variable dependency requires review

- Severity: warning; status: Requires Review; confidence: medium.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:a628d4b63ffaefa30197033e6666bb03c933358fb1265684d1cbe94bd2dedd68.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[4\].parameters{member:3}.
- Dependencies: dependency:6.
- Recommendation: Provision the n8n variable and verify feature availability and environment scope manually.

### WF013 — Local filesystem dependency requires review

- Severity: warning; status: Requires Review; confidence: medium.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:450573160e73ca696a989b07b59f7c0916fd0205bbe4c6dee6ebddcae4cf4107.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[5\].parameters{member:0}.
- Dependencies: dependency:7.
- Recommendation: Review destination mounts, file availability and permissions; do not read the path during analysis.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high.
- Workflow ID: workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41; node ID: node:sha256:70f98b081448d81453cdcf5a89241dd1e96d76be089b115b5966adc002861bcc.
- File: examples\\sprint2\\workflows\\B.json; evidence: $.nodes\[0\].parameters.workflowId.
- Dependencies: dependency:8.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF010 — Credential reference requires reconfiguration

- Severity: warning; status: Requires Reconfiguration; confidence: high.
- Workflow ID: workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41; node ID: node:sha256:1989824521ef1ae24368c024ea1d66441b50380a97ce553fb349e5fb9ad0440a.
- File: examples\\sprint2\\workflows\\B.json; evidence: $.nodes\[1\].credentials{member:0}.id.
- Dependencies: dependency:9.
- Recommendation: Recreate or securely map credentials on the destination; verify permissions without disclosing secrets.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high.
- Workflow ID: workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; node ID: node:sha256:e9577d6099228a0fce3f90934cc27bfd5f39b0c383af583012bd4b8d4e865bb3.
- File: examples\\sprint2\\workflows\\C.json; evidence: $.nodes\[0\].parameters.workflowId.value.
- Dependencies: dependency:11.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review: Missing From Import Set; destination existence is unknown

- Severity: warning; status: Missing From Import Set; confidence: high.
- Workflow ID: workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; node ID: node:sha256:4ec10f076432640578a22718cdc97472490f881e94dc41b27d2312f79e96fea3.
- File: examples\\sprint2\\workflows\\C.json; evidence: $.nodes\[1\].parameters.workflowId.value.
- Dependencies: dependency:12.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low.
- Workflow ID: workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; node ID: node:sha256:9cc5d82e418cbebc539488a87b1ed2ee71697015ccd7f65c054becd92a497ed3.
- File: examples\\sprint2\\workflows\\C.json; evidence: $.nodes\[2\].typeVersion.
- Dependencies: dependency:13.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF018 — Multiple nodes reference the same external resource identity; shared state is unverified

- Severity: info; status: Shared Resource Reference; confidence: medium.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:a628d4b63ffaefa30197033e6666bb03c933358fb1265684d1cbe94bd2dedd68.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[4\].credentials{member:0}.id.
- Dependencies: dependency:3, dependency:9.
- Recommendation: Review all linked references for shared quotas, ownership, state and migration sequencing.

### WF018 — Multiple nodes reference the same external resource identity; shared state is unverified

- Severity: info; status: Shared Resource Reference; confidence: medium.
- Workflow ID: workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; node ID: node:sha256:a628d4b63ffaefa30197033e6666bb03c933358fb1265684d1cbe94bd2dedd68.
- File: examples\\sprint2\\workflows\\A.json; evidence: $.nodes\[4\].parameters{member:0}.
- Dependencies: dependency:4, dependency:10.
- Recommendation: Review all linked references for shared quotas, ownership, state and migration sequencing.

## Dependency inventory

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:0 | error\_workflow | Found In Import Set | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.settings.errorWorkflow |
| dependency:1 | sub\_workflow | Found In Import Set | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[2\].parameters.workflowId.value |
| dependency:2 | sub\_workflow | Unknown | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[3\].parameters.workflowId.value |
| dependency:3 | credential | Requires Reconfiguration | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[4\].credentials{member:0}.id |
| dependency:4 | external\_service | Requires Review | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[4\].parameters{member:0} |
| dependency:5 | environment\_variable | Requires Review | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[4\].parameters{member:2} |
| dependency:6 | n8n\_variable | Requires Review | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[4\].parameters{member:3} |
| dependency:7 | local\_path | Requires Review | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[5\].parameters{member:0} |
| dependency:8 | sub\_workflow | Found In Import Set | workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41 | $.nodes\[0\].parameters.workflowId |
| dependency:9 | credential | Requires Reconfiguration | workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41 | $.nodes\[1\].credentials{member:0}.id |
| dependency:10 | external\_service | Requires Review | workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41 | $.nodes\[1\].parameters{member:0} |
| dependency:11 | sub\_workflow | Found In Import Set | workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | $.nodes\[0\].parameters.workflowId.value |
| dependency:12 | sub\_workflow | Missing From Import Set | workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | $.nodes\[1\].parameters.workflowId.value |
| dependency:13 | sub\_workflow | Unknown | workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | $.nodes\[2\].typeVersion |

## Unknown dependencies

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:2 | sub\_workflow | Unknown | workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875 | $.nodes\[3\].parameters.workflowId.value |
| dependency:13 | sub\_workflow | Unknown | workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | $.nodes\[2\].typeVersion |

## Missing From Import Set

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:12 | sub\_workflow | Missing From Import Set | workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525 | $.nodes\[1\].parameters.workflowId.value |

## Indirect static references

- workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875: unresolved-workflow:sha256:cf7299ef59acfa5964656c972cc59a27ef0561807e8f0a910ff17762bf6eab1d, workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525
- workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41: unresolved-workflow:sha256:cf7299ef59acfa5964656c972cc59a27ef0561807e8f0a910ff17762bf6eab1d, workflow:sha256:d14d26a907fe1c69f9b504a191bd038c719bc7f2528eb33d3d0ccc0da55d2119, workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875
- workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525: workflow:sha256:d14d26a907fe1c69f9b504a191bd038c719bc7f2528eb33d3d0ccc0da55d2119, workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41

## Human review

- WORKFLOW\_CYCLE\_REVIEW / Informational: Workflow references contain a cycle; review intended recursion and termination without assuming an error. (workflow None; evidence $; dependency None).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.settings.errorWorkflow; dependency dependency:0).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[2\].parameters.workflowId.value; dependency dependency:1).
- DEPENDENCY\_REVIEW / Unknown: Workflow reference requires runtime evaluation (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[3\].parameters.workflowId.value; dependency dependency:2).
- DEPENDENCY\_REVIEW / Requires Reconfiguration: Credential ID reference extracted; destination mapping is unverified (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[4\].credentials{member:0}.id; dependency dependency:3).
- DEPENDENCY\_REVIEW / Requires Review: Static service origin found; access and shared-state semantics are unverified (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[4\].parameters{member:0}; dependency dependency:4).
- DEPENDENCY\_REVIEW / Requires Review: Lexical variable access found; availability and value are unverified (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[4\].parameters{member:2}; dependency dependency:5).
- DEPENDENCY\_REVIEW / Requires Review: Lexical variable access found; availability and value are unverified (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[4\].parameters{member:3}; dependency dependency:6).
- DEPENDENCY\_REVIEW / Requires Review: Absolute path literal found; destination filesystem was not inspected (workflow workflow:sha256:f06c531ff4c0b38a0b100fbf4bf17beab9677b47794058a607046e5a010a6875; evidence $.nodes\[5\].parameters{member:0}; dependency dependency:7).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41; evidence $.nodes\[0\].parameters.workflowId; dependency dependency:8).
- DEPENDENCY\_REVIEW / Requires Reconfiguration: Credential ID reference extracted; destination mapping is unverified (workflow workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41; evidence $.nodes\[1\].credentials{member:0}.id; dependency dependency:9).
- DEPENDENCY\_REVIEW / Requires Review: Static service origin found; access and shared-state semantics are unverified (workflow workflow:sha256:e447185c597b15d0303d021852370286cca2e1b5e91e4e5ee5550e8d8fe02a41; evidence $.nodes\[1\].parameters{member:0}; dependency dependency:10).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; evidence $.nodes\[0\].parameters.workflowId.value; dependency dependency:11).
- DEPENDENCY\_REVIEW / Missing From Import Set: Static workflow ID extracted (workflow workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; evidence $.nodes\[1\].parameters.workflowId.value; dependency dependency:12).
- DEPENDENCY\_REVIEW / Unknown: Node version is not covered by a registered workflow-call adapter (workflow workflow:sha256:26357a9d02400629956f3979f39c404e96eb44320f20f67156e6560393669525; evidence $.nodes\[2\].typeVersion; dependency dependency:13).

## Excluded files


## Graphs

Graph JSON is available through `analyze --format graph-json` or the JSON report's `analysis.graphs` field.
Cross-workflow cyclic components: 1. Cycles are informational.

## Scope

Offline lexical and structural evidence only. Missing From Import Set does not mean missing on the destination. Cycles are informational. Unrecognized node semantics and runtime-computed dependencies remain unverified.

Static structural checks only; compatibility is unknown, not proof of successful import or execution.
