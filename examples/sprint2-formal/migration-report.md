# n8n Workflow Doctor — Migration dependency report

Input: examples\\sprint2-formal\\workflows

Batch complete: True; structural findings: 0; input errors: 0.


## Structural findings


## Summary

| Metric | Count |
| --- | --- |
| workflow\_count | 4 |
| excluded\_file\_count | 0 |
| node\_count | 13 |
| connection\_count | 6 |
| dependency\_count | 17 |
| static\_dependency\_count | 13 |
| unknown\_dependency\_count | 4 |
| missing\_resource\_count | 1 |
| risk\_count | 17 |
| manual\_review\_count | 18 |
| direct\_dependency\_count | 5 |
| indirect\_dependency\_count | 7 |
| blocking\_issue\_count | 0 |
| check\_count | 20 |

Compatibility: **unknown**. IDs are stable fingerprints; temporary file IDs are explicitly marked.

## Workflow identities

| Workflow ID | Identity kind | File |
| --- | --- | --- |
| workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | n8n\_id\_fingerprint | examples\\sprint2-formal\\workflows\\A.json |
| workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | n8n\_id\_fingerprint | examples\\sprint2-formal\\workflows\\B.json |
| workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30 | n8n\_id\_fingerprint | examples\\sprint2-formal\\workflows\\C.json |
| workflow:sha256:f1af265cfc31943b9ea016117a7f3179ab2829eba9d72090530f7d829f337952 | n8n\_id\_fingerprint | examples\\sprint2-formal\\workflows\\ERROR\_HANDLER.json |

## Migration risks

### WF009 — Error Workflow reference requires migration review

- Severity: info; status: Found In Import Set; confidence: high; assessment: verified.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: None.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.settings.errorWorkflow.
- Dependencies: dependency:0.
- Recommendation: Map the error workflow after import and verify its Error Trigger and permissions manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high; assessment: verified.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:d806d173fc86cc93718c828ecf53538f872d971bc4b205d75de37e7ecf1014bd.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[1\].parameters.workflowId.
- Dependencies: dependency:1.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review: Missing From Import Set; destination existence is unknown

- Severity: warning; status: Missing From Import Set; confidence: high; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:b7fb272828f6177d95e545da198f677a916b448f9f46ad971f08297f3db5c5ca.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[2\].parameters.workflowId.value.
- Dependencies: dependency:2.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low; assessment: unknown.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:a982a1c374fa06b7577d04ae9ed15d9a469a00f8cc28e225a10a755a21c10a07.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[3\].parameters.workflowId.value.
- Dependencies: dependency:3.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low; assessment: unknown.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:db68e0533976cf2ecf9fb70b5c83a179232f8b306a8b2f6d63eb70184bf163b3.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[4\].parameters.workflowPath.
- Dependencies: dependency:4.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF013 — Local filesystem dependency requires review

- Severity: warning; status: Requires Review; confidence: high; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:db68e0533976cf2ecf9fb70b5c83a179232f8b306a8b2f6d63eb70184bf163b3.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[4\].parameters.workflowPath.
- Dependencies: dependency:5.
- Recommendation: Review destination mounts, file availability and permissions; do not read the path during analysis.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low; assessment: unknown.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:b6b78d48751773011eaaa765090f5b5e031705a6bc8888ce7fd40365140d299d.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[5\].parameters.workflowJson.
- Dependencies: dependency:6.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF010 — Credential reference requires reconfiguration

- Severity: warning; status: Requires Reconfiguration; confidence: high; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].credentials{member:0}.id.
- Dependencies: dependency:7.
- Recommendation: Recreate or securely map credentials on the destination; verify permissions without disclosing secrets.

### WF012 — n8n variable dependency requires review

- Severity: warning; status: Requires Review; confidence: medium; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].parameters{member:2}.
- Dependencies: dependency:9.
- Recommendation: Provision the n8n variable and verify feature availability and environment scope manually.

### WF012 — Environment variable dependency requires review

- Severity: warning; status: Requires Review; confidence: medium; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].parameters{member:2}.
- Dependencies: dependency:10.
- Recommendation: Provision the required environment variable and check access policy; never copy its value into the report.

### WF013 — Local filesystem dependency requires review

- Severity: warning; status: Requires Review; confidence: medium; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].parameters{member:3}.
- Dependencies: dependency:11.
- Recommendation: Review destination mounts, file availability and permissions; do not read the path during analysis.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high; assessment: verified.
- Workflow ID: workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03; node ID: node:sha256:f1766143688ed3b8bc2fc7fdb73f45cf8585ad45271ef3fda46e35da44f71a2e.
- File: examples\\sprint2-formal\\workflows\\B.json; evidence: $.nodes\[0\].parameters.workflowId.value.
- Dependencies: dependency:12.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF010 — Credential reference requires reconfiguration

- Severity: warning; status: Requires Reconfiguration; confidence: high; assessment: risk.
- Workflow ID: workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03; node ID: node:sha256:612e3b216a2f7fdb5bc6cb41a391405eab7e1c8523dfb8065b638ef106491f97.
- File: examples\\sprint2-formal\\workflows\\B.json; evidence: $.nodes\[1\].credentials{member:0}.id.
- Dependencies: dependency:13.
- Recommendation: Recreate or securely map credentials on the destination; verify permissions without disclosing secrets.

### WF008 — Sub-workflow dependency requires migration review

- Severity: info; status: Found In Import Set; confidence: high; assessment: verified.
- Workflow ID: workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30; node ID: node:sha256:269884f51665e95cd75c1d55f2fa4e6e5b128cd23fb7f5f9aef2edc1060bc5ea.
- File: examples\\sprint2-formal\\workflows\\C.json; evidence: $.nodes\[0\].parameters.workflowId.value.
- Dependencies: dependency:15.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF008 — Sub-workflow dependency requires migration review

- Severity: warning; status: Unknown; confidence: low; assessment: unknown.
- Workflow ID: workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30; node ID: node:sha256:6b4d7bb0446154030590382e4db3ec7a6f42ab1b74c51b1e2fa2911f7b06f048.
- File: examples\\sprint2-formal\\workflows\\C.json; evidence: $.nodes\[1\].typeVersion.
- Dependencies: dependency:16.
- Recommendation: Map the workflow ID after import; check caller permissions, inputs and publication state manually.

### WF018 — Multiple nodes reference the same external resource identity; shared state is unverified

- Severity: info; status: Shared Resource Reference; confidence: medium; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].credentials{member:0}.id.
- Dependencies: dependency:7, dependency:13.
- Recommendation: Review all linked references for shared quotas, ownership, state and migration sequencing.

### WF018 — Multiple nodes reference the same external resource identity; shared state is unverified

- Severity: info; status: Shared Resource Reference; confidence: medium; assessment: risk.
- Workflow ID: workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; node ID: node:sha256:1673514a7877a1f149e1abc2dbf576ebdb30fe135ac6fa7ab0d427cfcb6891ab.
- File: examples\\sprint2-formal\\workflows\\A.json; evidence: $.nodes\[6\].parameters{member:0}.
- Dependencies: dependency:8, dependency:14.
- Recommendation: Review all linked references for shared quotas, ownership, state and migration sequencing.

## Dependency inventory

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:0 | error\_workflow | Found In Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.settings.errorWorkflow |
| dependency:1 | sub\_workflow | Found In Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[1\].parameters.workflowId |
| dependency:2 | sub\_workflow | Missing From Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[2\].parameters.workflowId.value |
| dependency:3 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[3\].parameters.workflowId.value |
| dependency:4 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[4\].parameters.workflowPath |
| dependency:5 | local\_path | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[4\].parameters.workflowPath |
| dependency:6 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[5\].parameters.workflowJson |
| dependency:7 | credential | Requires Reconfiguration | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].credentials{member:0}.id |
| dependency:8 | external\_service | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:0} |
| dependency:9 | n8n\_variable | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:2} |
| dependency:10 | environment\_variable | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:2} |
| dependency:11 | local\_path | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:3} |
| dependency:12 | sub\_workflow | Found In Import Set | workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | $.nodes\[0\].parameters.workflowId.value |
| dependency:13 | credential | Requires Reconfiguration | workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | $.nodes\[1\].credentials{member:0}.id |
| dependency:14 | external\_service | Requires Review | workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | $.nodes\[1\].parameters{member:0} |
| dependency:15 | sub\_workflow | Found In Import Set | workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30 | $.nodes\[0\].parameters.workflowId.value |
| dependency:16 | sub\_workflow | Unknown | workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30 | $.nodes\[1\].typeVersion |

## Direct cross-workflow dependencies

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:0 | error\_workflow | Found In Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.settings.errorWorkflow |
| dependency:1 | sub\_workflow | Found In Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[1\].parameters.workflowId |
| dependency:2 | sub\_workflow | Missing From Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[2\].parameters.workflowId.value |
| dependency:12 | sub\_workflow | Found In Import Set | workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | $.nodes\[0\].parameters.workflowId.value |
| dependency:15 | sub\_workflow | Found In Import Set | workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30 | $.nodes\[0\].parameters.workflowId.value |

## Credential checklist

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:7 | credential | Requires Reconfiguration | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].credentials{member:0}.id |
| dependency:13 | credential | Requires Reconfiguration | workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03 | $.nodes\[1\].credentials{member:0}.id |

## Variable checklist

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:9 | n8n\_variable | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:2} |
| dependency:10 | environment\_variable | Requires Review | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[6\].parameters{member:2} |

## Unknown dependencies

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:3 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[3\].parameters.workflowId.value |
| dependency:4 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[4\].parameters.workflowPath |
| dependency:6 | sub\_workflow | Unknown | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[5\].parameters.workflowJson |
| dependency:16 | sub\_workflow | Unknown | workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30 | $.nodes\[1\].typeVersion |

## Missing From Import Set

| Dependency | Kind | Status | Workflow | Evidence |
| --- | --- | --- | --- | --- |
| dependency:2 | sub\_workflow | Missing From Import Set | workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563 | $.nodes\[2\].parameters.workflowId.value |

## Assessment checks

Verified means verified within this input set only; destination compatibility remains unknown.

- WF009 / verified: Error Workflow reference requires migration review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.settings.errorWorkflow).
- WF008 / verified: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[1\].parameters.workflowId).
- WF008 / risk: Sub-workflow dependency requires migration review: Missing From Import Set; destination existence is unknown (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[2\].parameters.workflowId.value).
- WF008 / unknown: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[3\].parameters.workflowId.value).
- WF008 / unknown: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[4\].parameters.workflowPath).
- WF013 / risk: Local filesystem dependency requires review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[4\].parameters.workflowPath).
- WF008 / unknown: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[5\].parameters.workflowJson).
- WF010 / risk: Credential reference requires reconfiguration (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].credentials{member:0}.id).
- WF012 / risk: n8n variable dependency requires review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].parameters{member:2}).
- WF012 / risk: Environment variable dependency requires review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].parameters{member:2}).
- WF013 / risk: Local filesystem dependency requires review (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].parameters{member:3}).
- WF008 / verified: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\B.json; evidence $.nodes\[0\].parameters.workflowId.value).
- WF010 / risk: Credential reference requires reconfiguration (file examples\\sprint2-formal\\workflows\\B.json; evidence $.nodes\[1\].credentials{member:0}.id).
- WF008 / verified: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\C.json; evidence $.nodes\[0\].parameters.workflowId.value).
- WF008 / unknown: Sub-workflow dependency requires migration review (file examples\\sprint2-formal\\workflows\\C.json; evidence $.nodes\[1\].typeVersion).
- WF018 / risk: Multiple nodes reference the same external resource identity; shared state is unverified (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].credentials{member:0}.id).
- WF018 / risk: Multiple nodes reference the same external resource identity; shared state is unverified (file examples\\sprint2-formal\\workflows\\A.json; evidence $.nodes\[6\].parameters{member:0}).
- WF009 / not\_applicable: No explicit external Error Workflow is configured (file examples\\sprint2-formal\\workflows\\B.json; evidence $.settings.errorWorkflow).
- WF009 / not\_applicable: No explicit external Error Workflow is configured (file examples\\sprint2-formal\\workflows\\C.json; evidence $.settings.errorWorkflow).
- WF009 / not\_applicable: No explicit external Error Workflow is configured (file examples\\sprint2-formal\\workflows\\ERROR\_HANDLER.json; evidence $.settings.errorWorkflow).
## Indirect static references

- workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563: workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30
- workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03: unresolved-workflow:sha256:6482a57d52af81b4459efb535f4caad13ec595c275da6554a218e82c658d9148, workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563, workflow:sha256:f1af265cfc31943b9ea016117a7f3179ab2829eba9d72090530f7d829f337952
- workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30: unresolved-workflow:sha256:6482a57d52af81b4459efb535f4caad13ec595c275da6554a218e82c658d9148, workflow:sha256:f1af265cfc31943b9ea016117a7f3179ab2829eba9d72090530f7d829f337952, workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03

## Human review

- WORKFLOW\_CYCLE\_REVIEW / Informational: Workflow references contain a cycle; review intended recursion and termination without assuming an error. (workflow None; evidence $; dependency None).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.settings.errorWorkflow; dependency dependency:0).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[1\].parameters.workflowId; dependency dependency:1).
- DEPENDENCY\_REVIEW / Missing From Import Set: Static workflow ID extracted (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[2\].parameters.workflowId.value; dependency dependency:2).
- DEPENDENCY\_REVIEW / Unknown: Workflow reference requires runtime evaluation (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[3\].parameters.workflowId.value; dependency dependency:3).
- DEPENDENCY\_REVIEW / Unknown: File-sourced workflow is not a database ID; file content was not read (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[4\].parameters.workflowPath; dependency dependency:4).
- DEPENDENCY\_REVIEW / Requires Review: Explicit workflow file dependency; no file was read (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[4\].parameters.workflowPath; dependency dependency:5).
- DEPENDENCY\_REVIEW / Unknown: Parameterized workflow is not a database ID; embedded content was not evaluated (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[5\].parameters.workflowJson; dependency dependency:6).
- DEPENDENCY\_REVIEW / Requires Reconfiguration: Credential ID reference extracted; destination mapping is unverified (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[6\].credentials{member:0}.id; dependency dependency:7).
- DEPENDENCY\_REVIEW / Requires Review: Static service origin found; access and shared-state semantics are unverified (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[6\].parameters{member:0}; dependency dependency:8).
- DEPENDENCY\_REVIEW / Requires Review: Lexical variable access found; availability and value are unverified (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[6\].parameters{member:2}; dependency dependency:9).
- DEPENDENCY\_REVIEW / Requires Review: Lexical variable access found; availability and value are unverified (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[6\].parameters{member:2}; dependency dependency:10).
- DEPENDENCY\_REVIEW / Requires Review: Absolute path literal found; destination filesystem was not inspected (workflow workflow:sha256:26b3e9af78c33d0235bf9b0b6b9a2c86d153fef24845aece049f0471e3903563; evidence $.nodes\[6\].parameters{member:3}; dependency dependency:11).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03; evidence $.nodes\[0\].parameters.workflowId.value; dependency dependency:12).
- DEPENDENCY\_REVIEW / Requires Reconfiguration: Credential ID reference extracted; destination mapping is unverified (workflow workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03; evidence $.nodes\[1\].credentials{member:0}.id; dependency dependency:13).
- DEPENDENCY\_REVIEW / Requires Review: Static service origin found; access and shared-state semantics are unverified (workflow workflow:sha256:ff08714089339bbcfeb0f716904bd43d3cd18d35473f75e9cfe42e8410602e03; evidence $.nodes\[1\].parameters{member:0}; dependency dependency:14).
- DEPENDENCY\_REVIEW / Found In Import Set: Static workflow ID extracted (workflow workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30; evidence $.nodes\[0\].parameters.workflowId.value; dependency dependency:15).
- DEPENDENCY\_REVIEW / Unknown: Node version is not covered by a registered workflow-call adapter (workflow workflow:sha256:f065f5436288e0eb65d1b2644b4a81c2a57ed25e2d80015b61e6bb78f612be30; evidence $.nodes\[1\].typeVersion; dependency dependency:16).

## Excluded files


## Graphs

Graph JSON is available through `analyze --format graph-json` or the JSON report's `analysis.graphs` field.
Cross-workflow cyclic components: 1. Cycles are informational.

## Scope

Offline lexical and structural evidence only. Missing From Import Set does not mean missing on the destination. Cycles are informational. Unrecognized node semantics and runtime-computed dependencies remain unverified.

Static structural checks only; compatibility is unknown, not proof of successful import or execution.
