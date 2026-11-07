export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail :
      Array.isArray(detail) ? detail.map((issue: { msg?: string }) => issue.msg || 'Dữ liệu không hợp lệ').join('; ') :
      typeof detail === 'object' && detail !== null && 'message' in detail && typeof detail.message === 'string'
        ? detail.message : 'Yêu cầu thất bại.');
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch('/api' + path, {
      cache: 'no-store', ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    });
  } catch {
    throw new ApiError(0, 'Không kết nối được backend FastAPI. Hãy kiểm tra server Python.');
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new ApiError(res.status, payload.detail || payload.message || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function download(path: string, filename: string): Promise<void> {
  const res = await fetch('/api' + path, { cache: 'no-store' });
  if (!res.ok) throw new Error('Không tải được tập tin.');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export async function copyClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(text); return; } catch { /* fallback below */ }
  }
  const el = document.createElement('textarea');
  el.value = text;
  el.setAttribute('readonly', '');
  el.style.position = 'fixed';
  el.style.left = '-9999px';
  document.body.appendChild(el);
  el.select();
  const ok = document.execCommand('copy');
  el.remove();
  if (!ok) throw new Error('Trình duyệt từ chối truy cập clipboard. Sử dụng HTTPS hoặc localhost.');
}
