export const assessmentLabels: Record<string, string> = {
  verified: '静态检查通过（限定范围）', blocked: '明确阻断', risk: '存在风险',
  unknown: '静态分析无法判定', not_applicable: '不适用',
}
export function visible(value: unknown): string {
  // Expose bidi/invisible controls; Vue still escapes all markup in interpolation.
  return String(value ?? '').replace(/[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b-\u200f\u2028-\u202e\u2060-\u206f\ud800-\udfff\ufeff]/gu,
    char => `[U+${char.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}]`)
}
export const shortId = (id: unknown) => visible(id).length > 30 ? `${visible(id).slice(0, 18)}…${visible(id).slice(-8)}` : visible(id)
export const validId = (id: unknown): id is string => typeof id === 'string' && /^[a-f0-9]{32}$/.test(id)
export function workflowLabel(id: string | null, workflows: { workflow_id: string }[]) {
  const index = workflows.findIndex(w => w.workflow_id === id)
  return index < 0 ? (id ? '集合外工作流' : '文件级检查') : `工作流 ${index + 1}`
}
