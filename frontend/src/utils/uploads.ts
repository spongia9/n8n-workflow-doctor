export const MAX_FILES = 32
export const MAX_JSON = 2 * 1024 * 1024
// Reserve 64 KiB for browser multipart boundaries and filenames under the 8 MiB request cap.
export const MAX_UPLOAD = 8 * 1024 * 1024 - 64 * 1024
export function validateFiles(files: readonly File[]): string | null {
  if (!files.length) return '请选择 JSON 文件或单个 ZIP。'
  if (files.length > MAX_FILES) return '最多选择 32 个 JSON 文件。'
  let bytes = 0; let zips = 0
  for (const file of files) {
    if (file.name.length > 255 || /[/\\:\p{Cc}\p{Cf}]/u.test(file.name)) return '文件名包含路径或不可见字符，请使用普通文件名。'
    const suffix = file.name.split('.').pop()?.toLowerCase()
    if (!['json', 'zip'].includes(suffix || '')) return '仅支持 .json 和 .zip 文件。'
    if (!file.size) return '不能上传空文件。'
    if (suffix === 'zip') zips++
    else if (file.size > MAX_JSON) return '单个 JSON 不能超过 2 MiB。'
    bytes += file.size
  }
  if (zips && files.length !== 1) return 'ZIP 必须单独上传，不能与其他文件混合。'
  if (bytes > MAX_UPLOAD) return '上传总量过大，请控制在 7.93 MiB 以内。'
  return null
}
