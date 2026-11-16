import { describe, it, expect, vi } from 'vitest'
import { ApiError, decodeJson, localBase, request } from '../src/api/client'
import { scanResponse, reportFilename, createScan, getReport, getScan } from '../src/api/scans'
import { metadata } from './factories'
import { validateFiles, MAX_JSON, MAX_UPLOAD } from '../src/utils/uploads'
import { visible } from '../src/utils/display'
describe('actual contract client / mocked transport', () => {
  it('allows only explicit loopback HTTP origins', () => {
    expect(localBase('http://127.0.0.1:8001')).toBe('http://127.0.0.1:8001')
    for (const v of ['https://example.com', 'http://localhost.evil.test', 'http://user@localhost', 'http://localhost/x']) expect(() => localBase(v)).toThrow()
  })
  it('resolves same-origin deployments locally and rejects a public page origin', () => {
    const original = window
    // jsdom's default URL is localhost; configured production origin is checked
    // by the same localBase validator as explicitly configured development URLs.
    expect(localBase('same-origin')).toBe(window.location.origin)
    vi.stubGlobal('window', { location: { origin: 'https://public.invalid' } })
    try { expect(() => localBase('same-origin')).toThrow() } finally { vi.stubGlobal('window', original) }
    expect(() => localBase('https://public.invalid')).toThrow()
  })
  it('sanitizes errors instead of displaying response text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('SYNTHETIC_PASSWORD', { status: 500 })))
    await expect(request('/health')).rejects.toMatchObject({ status: 500 })
    try { await request('/health') } catch (e) { expect(String(e)).not.toContain('SYNTHETIC_PASSWORD') }
  })
  it.each([400, 403, 404, 408, 413, 415, 422, 503])('retains HTTP %s for safe error handling', async status => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status })))
    await expect(request('/health')).rejects.toMatchObject({ status })
  })
  it('identifies network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private diagnostic')))
    await expect(request('/health')).rejects.toMatchObject({ code: 'NETWORK' })
  })
  it('requires a valid response envelope', () => { expect(() => scanResponse({ status: 'running' })).toThrow(ApiError) })
  it('rejects damaged JSON without copying contents', () => { expect(() => decodeJson(new TextEncoder().encode('{private'))).toThrow('数据格式') })
  it('uses safe download filenames', () => {
    expect(reportFilename('a'.repeat(32), 'html', 'attachment; filename="../../evil.html"')).toBe(`scan-${'a'.repeat(32)}.html`)
  })
  it('accepts single, multiple JSON and ZIP selections', () => {
    const json = new File(['{}'], '中文.json')
    expect(validateFiles([json])).toBeNull(); expect(validateFiles([json, json])).toBeNull()
    expect(validateFiles([new File(['fake'], 'sample.zip')])).toBeNull()
  })
  it('rejects empty, mixed, excessive and unsafe selections', () => {
    const json = new File(['{}'], 'a.json'); const zip = new File(['zip'], 'a.zip')
    for (const files of [[], [new File([], 'a.json')], [json, zip], Array(33).fill(json), [new File(['a'], 'a.exe')], [new File(['a'], '../a.json')], [new File(['a'], 'a\u202e.json')]]) expect(validateFiles(files)).toBeTruthy()
  })
  it('enforces byte limits', () => {
    expect(validateFiles([new File([new Uint8Array(MAX_JSON + 1)], 'a.json')])).toContain('2 MiB')
    expect(validateFiles([new File([new Uint8Array(MAX_UPLOAD + 1)], 'a.zip')])).toContain('总量')
  })
  it('makes invisible controls visible and preserves Chinese text', () => { expect(visible('中文\u202e<script>')).toBe('中文[U+202E]<script>') })
  it('exposes lone surrogates while preserving normal emoji', () => { expect(visible('中文😀\ud800')).toBe('中文😀[U+D800]') })
  it('uses the real multipart files field without adding a boundary header', async () => {
    const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify(metadata())))
    vi.stubGlobal('fetch', mock)
    await createScan([new File(['{}'], 'a.json'), new File(['{}'], 'b.json')])
    const init = mock.mock.calls[0][1] as RequestInit
    expect((init.body as FormData).getAll('files')).toHaveLength(2)
    expect(init.headers).toBeUndefined(); expect(init.credentials).toBe('omit')
  })
  it('rejects path-shaped scan IDs before making requests', async () => {
    const mock = vi.fn(); vi.stubGlobal('fetch', mock)
    await expect(getScan('../../etc')).rejects.toMatchObject({ status: 404 }); expect(mock).not.toHaveBeenCalled()
  })
  it('rejects an unexpected report MIME', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('text', { headers: { 'Content-Type': 'text/javascript' } })))
    await expect(getReport('a'.repeat(32), 'html')).rejects.toMatchObject({ code: 'CONTRACT' })
  })
  it('bounds response bytes even before reading a declared oversized response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('small', { headers: { 'Content-Length': String(17 * 1024 * 1024) } })))
    await expect(request('/health')).rejects.toMatchObject({ status: 413 })
  })
  it('aborts timed-out fetch without automatically retrying', async () => {
    const mock = vi.fn((_url, init: RequestInit) => new Promise<Response>((_resolve, reject) => init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))))
    vi.stubGlobal('fetch', mock)
    await expect(request('/health', {}, 5)).rejects.toMatchObject({ code: 'TIMEOUT' }); expect(mock).toHaveBeenCalledTimes(1)
  })
})
