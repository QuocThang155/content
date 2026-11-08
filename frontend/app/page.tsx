'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import {
  Activity, AlertCircle, ArrowRight, BadgeCheck, BookOpen, CalendarDays, ChevronRight,
  Check, CheckCircle2, CircleHelp, Clipboard, CloudDownload,
  Database, Download, FileJson, FileText, Filter, History, LayoutDashboard,
  ImageIcon, Layers, LoaderCircle, Pencil, Plus, RefreshCw, RotateCcw, Search,
  Settings2, ShieldCheck, Sparkles, WandSparkles, X, Zap,
} from 'lucide-react';
import { api, ApiError, copyClipboard, download } from '@/lib/api';
import type {
  BriefFields, Duplicate, HistoryData, Mode, Overview, Pair, PlanConflict, Story, Tab,
  WorkspaceConfig, WorkspaceFile, WorkspaceItem, PromptMode, PromptTemplates,
} from '@/lib/types';

const FIELD_LABELS: { key: keyof BriefFields; label: string; placeholder: string }[] = [
  { key: 'title', label: 'Tiêu đề', placeholder: 'Tên truyện' },
  { key: 'hero', label: 'Nhân vật chính', placeholder: 'Ai là nhân vật chính?' },
  { key: 'antagonist', label: 'Nhân vật phản diện', placeholder: 'Ai gây ra xung đột?' },
  { key: 'conflict', label: 'Hành động bất công', placeholder: 'Mô tả hành động cụ thể' },
  { key: 'evidence', label: 'Bằng chứng', placeholder: 'Bằng chứng xác minh được' },
  { key: 'reversal', label: 'Cú đảo chiều', placeholder: 'Bằng chứng làm thay đổi tình thế thế nào?' },
  { key: 'ending', label: 'Kết thúc', placeholder: 'Kết thúc hợp lý, thỏa đáng' },
];
const STATUSES: Record<string, string> = { ready: 'Chưa giao', sent: 'Đã giao', part1: 'Đã có Part 1', done: 'Hoàn tất' };
const emptyStats = { total: 0, done: 0, in_progress: 0, ready: 0, sent: 0, part1: 0 };
const emptyOverview: Overview = { date: '', exists: false, items: [], stats: emptyStats,
  theme_names: {}, library_size: 0, ideas_remaining: 0, starter_used: 0, starter_total: 84, days_count: 0 };

function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function prettyDate(date: string): string {
  if (!date) return '';
  const [y, m, d] = date.split('-');
  return `${d}/${m}/${y}`;
}
function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi không xác định.';
}
function briefPayload(item: Story): BriefFields {
  return { title: item.title, hero: item.hero, antagonist: item.antagonist, conflict: item.conflict,
    evidence: item.evidence, reversal: item.reversal, ending: item.ending };
}
function laneSlot(item: Pick<Story, 'slot' | 'lane_slot' | 'ai'>): number {
  return item.lane_slot ?? item.slot - (item.ai - 1) * 14;
}

function statsForItems(items: Story[]): Overview['stats'] {
  const counts = items.reduce((result, item) => {
    result[item.status] += 1;
    return result;
  }, { ready: 0, sent: 0, part1: 0, done: 0 } as Record<Story['status'], number>);
  return {
    total: items.length,
    done: counts.done,
    in_progress: counts.sent + counts.part1,
    ready: counts.ready,
    sent: counts.sent,
    part1: counts.part1,
  };
}

type Notice = { text: string; type: 'success' | 'error' | 'info' };
type SimilarityReport = { title: string; rows: { left: string; right?: string; score: number }[] };

export default function ThangMiaPage() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const [date, setDate] = useState(localToday);
  const [overview, setOverview] = useState<Overview>(emptyOverview);
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [archivedItems, setArchivedItems] = useState<(Story & { date: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [unavailable, setUnavailable] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'ready' | 'active' | 'done'>('all');
  const [vaultSort, setVaultSort] = useState<'slot' | 'title' | 'status'>('slot');
  const [vaultCollapsed, setVaultCollapsed] = useState<Record<1 | 2 | 3, boolean>>({ 1: false, 2: false, 3: false });
  const [editing, setEditing] = useState<Story | null>(null);
  const [archiveViewer, setArchiveViewer] = useState<{
    item: Story & { date: string };
    output: WorkspaceFile | null;
    imageUrl: string;
    imageExists: boolean;
    imageWarning?: string;
  } | null>(null);
  const [form, setForm] = useState<BriefFields | null>(null);
  const [report, setReport] = useState<SimilarityReport | null>(null);
  const [plannerAi, setPlannerAi] = useState<1 | 2 | 3>(1);
  const [plannerText, setPlannerText] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [laneCursors, setLaneCursors] = useState<Record<1 | 2 | 3, number>>({ 1: 0, 2: 0, 3: 0 });
  const [laneViewAll, setLaneViewAll] = useState<Record<1 | 2 | 3, boolean>>({ 1: false, 2: false, 3: false });
  const [workspaceStatus, setWorkspaceStatus] = useState<Record<number, WorkspaceItem[]>>({});
  const [workspaceConfig, setWorkspaceConfig] = useState<WorkspaceConfig | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [configFolder, setConfigFolder] = useState('');
  const [fileViewer, setFileViewer] = useState<{
    item: Story; kind: 'prompt' | 'image_prompt' | 'output'; content: string; hash: string | null; filename: string; exists: boolean; warning?: string;
  } | null>(null);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplates>({ full: '', part1: '', part2: '', image: '' });
  const [promptDrafts, setPromptDrafts] = useState<PromptTemplates>({ full: '', part1: '', part2: '', image: '' });
  const [promptMode, setPromptMode] = useState<PromptMode>('full');
  const [promptPreview, setPromptPreview] = useState('');
  const [promptPreviewUid, setPromptPreviewUid] = useState('');
  const [promptLoading, setPromptLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function toast(text: string, type: Notice['type'] = 'success') { setNotice({ text, type }); }
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const refresh = useCallback(async (target: string, autoCreate: boolean) => {
    if (!target) return;
    setLoading(true);
    try {
      let data = await api<Overview>('/overview?date=' + encodeURIComponent(target));
      if (!data.exists && autoCreate) {
        try {
          await api('/days', { method: 'POST', body: JSON.stringify({ date: target }) });
          data = await api<Overview>('/overview?date=' + encodeURIComponent(target));
          setUnavailable('');
        } catch (err) {
          if (err instanceof ApiError && err.status === 409 && err.message.includes('đã tồn tại')) {
            data = await api<Overview>('/overview?date=' + encodeURIComponent(target));
          } else {
            setUnavailable(messageOf(err));
          }
        }
      } else if (data.exists) setUnavailable('');
      setOverview(data);
    } catch (err) { toast(messageOf(err), 'error'); }
    finally { setLoading(false); }
  }, []);

  // This effect synchronizes the selected date with the backend.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (date) void refresh(date, true); }, [date, refresh]);
  const refreshHistory = useCallback(async () => {
    try { setHistory(await api<HistoryData>('/history')); }
    catch (err) { toast(messageOf(err), 'error'); }
  }, []);
  const refreshWorkspace = useCallback(async () => {
    if (!overview.exists || !['workflow', 'vault'].includes(tab)) return;
    try {
      const statuses = await Promise.all(([1, 2, 3] as const).map((ai) =>
        api<{ items: WorkspaceItem[] }>(`/workspace/status?date=${date}&ai=${ai}`)));
      setWorkspaceStatus(Object.fromEntries(statuses.map((status, index) => [index + 1, status.items])));
    } catch (err) { toast(messageOf(err), 'error'); }
  }, [date, overview.exists, tab]);
  // Workspace status is polled while Workflow or Kho ý tưởng is open.
  useEffect(() => {
    if (!['workflow', 'vault'].includes(tab) || !overview.exists) return;
    // Polling synchronizes external workspace files while either view is open.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshWorkspace();
    const timer = window.setInterval(() => void refreshWorkspace(), 5000);
    return () => window.clearInterval(timer);
  }, [overview.exists, refreshWorkspace, tab]);
  // This effect loads history when its tab becomes active.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (tab === 'history') void refreshHistory(); }, [tab, refreshHistory]);
  useEffect(() => {
    if (tab !== 'archive') return;
    void api<{ items: (Story & { date: string })[] }>('/archive')
      .then((result) => setArchivedItems(result.items))
      .catch((err) => toast(messageOf(err), 'error'));
  }, [tab]);

  async function execute(key: string, action: () => Promise<void>) {
    if (working) return;
    setWorking(key);
    try { await action(); }
    catch (err) { toast(messageOf(err), 'error'); }
    finally { setWorking(''); }
  }

  async function copyStory(item: Story, mode: Mode) {
    await execute(`copy-${item.uid}`, async () => {
      // Full prompts are preloaded with overview so clipboard access happens during the click gesture.
      const promptText = mode === 'full' && item.full_prompt ? item.full_prompt :
        (await api<{ text: string }>(`/days/${date}/items/${item.uid}/prompt?mode=${mode}`)).text;
      await copyClipboard(promptText); // only update status AFTER browser confirms copy
      try {
        const result = await api<{ status: Story['status']; ideas_remaining: number }>(`/days/${date}/items/${item.uid}/copied`,
          { method: 'POST', body: JSON.stringify({ mode }) });
        setOverview((current) => {
          const items = current.items.map((currentItem) =>
            currentItem.uid === item.uid ? { ...currentItem, status: result.status } : currentItem);
          return { ...current, items, stats: statsForItems(items), ideas_remaining: result.ideas_remaining };
        });
        toast(`Đã sao chép ${mode === 'full' ? 'prompt toàn truyện' : mode.toUpperCase()} · ${item.title}`);
      } catch (err) {
        toast('Đã sao chép prompt nhưng chưa lưu được trạng thái: ' + messageOf(err), 'error');
      }
    });
  }

  async function copyReturnedStory(item: Story) {
    await execute(`copy-output-${item.uid}`, async () => {
      const result = await api<WorkspaceFile>(
        `/workspace/file?date=${date}&ai=${item.ai}&slot=${laneSlot(item)}&kind=output`,
      );
      if (!result.exists) throw new Error('Chưa có truyện trả về để sao chép.');
      await copyClipboard(result.content);
      try {
        const saved = await api<{ status: Story['status']; ideas_remaining: number }>(
          `/days/${date}/items/${item.uid}/output-copied`, { method: 'POST' });
        setOverview((current) => {
          const items = current.items.map((currentItem) =>
            currentItem.uid === item.uid ? { ...currentItem, status: saved.status } : currentItem);
          return { ...current, items, stats: statsForItems(items), ideas_remaining: saved.ideas_remaining };
        });
        toast(`Đã sao chép truyện trả về · ${item.title}`);
      } catch (err) {
        toast('Đã sao chép truyện trả về nhưng chưa ghi nhận hoàn tất: ' + messageOf(err), 'error');
      }
    });
  }

  async function archiveDoneAndMove(ai: 1 | 2 | 3, item: Story | undefined, currentIndex: number, itemCount: number) {
    await execute(`archive-next-${ai}`, async () => {
      const wasDone = item?.status === 'done';
      if (item?.status === 'done') {
        await api(`/days/${date}/items/${item.uid}/archive`, { method: 'POST' });
        setArchivedItems((current) => [...current, { ...item, date, archived_at: new Date().toISOString() }]);
        await refresh(date, false);
        toast(`Đã chuyển “${item.title}” vào Kho lưu trữ.`);
      }
      const nextCount = wasDone ? itemCount - 1 : itemCount;
      const nextIndex = nextCount > 0
        ? (wasDone ? currentIndex % nextCount : (currentIndex + 1) % nextCount)
        : 0;
      setLaneCursors((current) => ({ ...current, [ai]: nextIndex }));
    });
  }

  function copyNext(ai: number) {
    const item = overview.items.find((x) => x.ai === ai && x.status === 'ready');
    if (!item) return toast(`AI ${ai} không còn thẻ chưa giao.`, 'info');
    void copyStory(item, 'full');
  }

  async function toggleDone(item: Story) {
    await execute(`done-${item.uid}`, async () => {
      await api(`/days/${date}/items/${item.uid}/toggle-done`, { method: 'POST' });
      await refresh(date, false);
      toast(item.status === 'done' ? 'Đã hoàn tác.' : 'Đã đánh dấu hoàn tất.');
    });
  }

  async function deleteIdea(item: Story) {
    if (item.status !== 'ready') {
      toast('Chỉ có thể xóa bài chưa giao.', 'error');
      return;
    }
    if (!window.confirm(`Xóa vĩnh viễn bài “${item.title}” khỏi Kho ý tưởng?`)) return;
    await execute(`delete-${item.uid}`, async () => {
      const result = await api<{ ideas_remaining: number }>(`/days/${date}/items/${item.uid}`, { method: 'DELETE' });
      setOverview((current) => {
        const items = current.items.filter((candidate) => candidate.uid !== item.uid);
        return { ...current, items, stats: statsForItems(items), ideas_remaining: result.ideas_remaining };
      });
      toast(`Đã xóa bài khỏi Kho ý tưởng · ${item.title}`);
    });
  }

  async function updateMetadata(item: Story, changes: { notes?: string; favorite?: boolean; draft?: boolean }) {
    await execute(`metadata-${item.uid}`, async () => {
      const result = await api<{ item: Story }>(`/days/${date}/items/${item.uid}/metadata`, {
        method: 'PATCH',
        body: JSON.stringify({
          notes: changes.notes ?? item.notes ?? '',
          favorite: changes.favorite ?? item.favorite ?? false,
          draft: changes.draft ?? item.draft ?? false,
        }),
      });
      setOverview((current) => ({ ...current, items: current.items.map((candidate) =>
        candidate.uid === item.uid ? result.item : candidate) }));
      toast('Đã lưu thông tin Kho ý tưởng.');
    });
  }

  async function undoCopied(item: Story) {
    await execute(`undo-copy-${item.uid}`, async () => {
      const result = await api<{ status: Story['status']; ideas_remaining: number }>(
        `/days/${date}/items/${item.uid}/undo-copied`, { method: 'POST' });
      setOverview((current) => {
        const items = current.items.map((currentItem) =>
          currentItem.uid === item.uid ? { ...currentItem, status: result.status, last_copied: undefined } : currentItem);
        return { ...current, items, stats: statsForItems(items), ideas_remaining: result.ideas_remaining };
      });
      toast(`Đã hoàn tác sao chép · ${item.title}`);
    });
  }

  function openEditor(item: Story) {
    const fileStatus = workspaceStatus[item.ai]?.find((entry) => entry.slot === laneSlot(item));
    if (fileStatus?.prompt_exists || fileStatus?.output_exists) {
      toast('Brief đã có file TXT/output. Sửa brief không tự xóa hoặc ghi đè file cũ.', 'info');
    }
    setEditing(item); setForm(briefPayload(item));
  }
  async function saveEdit(close = true): Promise<void> {
    if (!editing || !form) return;
    if (Object.values(form).some((x) => x.trim().length < 7)) {
      toast('Mỗi trường cần ít nhất 7 ký tự.', 'error'); return;
    }
    await execute('save-edit', async () => {
      const result = await api<{ item: Story }>(`/days/${date}/items/${editing.uid}/brief`,
        { method: 'PATCH', body: JSON.stringify(form) });
      await refresh(date, false);
      setEditing(result.item);
      if (close) { setEditing(null); setForm(null); }
      toast('Đã lưu thông tin cốt truyện.');
    });
  }
  async function saveAndCopy(mode: Mode) {
    if (!editing || !form) return;
    if (Object.values(form).some((x) => x.trim().length < 7)) {
      toast('Mỗi trường cần ít nhất 7 ký tự.', 'error'); return;
    }
    await execute('edit-copy', async () => {
      await api(`/days/${date}/items/${editing.uid}/brief`,
        { method: 'PATCH', body: JSON.stringify(form) });
      const result = await api<{ text: string }>(`/days/${date}/items/${editing.uid}/prompt?mode=${mode}`);
      await copyClipboard(result.text);
      try {
        await api(`/days/${date}/items/${editing.uid}/copied`,
          { method: 'POST', body: JSON.stringify({ mode }) });
        toast(`Đã lưu và sao chép prompt ${mode === 'full' ? 'toàn truyện' : mode.toUpperCase()}.`);
      } catch (err) {
        toast('Prompt đã sao chép nhưng chưa lưu được trạng thái: ' + messageOf(err), 'error');
      }
      await refresh(date, false);
      setEditing(null);
      setForm(null);
    });
  }

  async function scanEdited() {
    if (!editing || !form) return;
    await execute('scan-edit', async () => {
      const result = await api<{ matches: Duplicate[] }>(`/days/${date}/items/${editing.uid}/scan`,
        { method: 'POST', body: JSON.stringify(form) });
      setReport({ title: `Kiểm tra gần giống · #${editing.slot}`,
        rows: result.matches.map((x) => ({ left: x.title, score: x.score })) });
    });
  }
  async function scanToday() {
    if (!overview.items.length) return toast('Ngày này chưa có thẻ để rà soát.', 'info');
    await execute('scan-all', async () => {
      const result = await api<{ pairs: Pair[]; total: number }>(`/days/${date}/scan`);
      setReport({ title: `Rà trùng ý tưởng · ${prettyDate(date)}`,
        rows: result.pairs.map((x) => ({ left: `#${x.first.slot} ${x.first.title}`,
          right: `#${x.second.slot} ${x.second.title}`, score: x.score })) });
    });
  }
  async function copyPlanningPrompt() {
    await execute('plan-copy', async () => {
      const r = await api<{ text: string }>(`/planning-prompt?date=${date}&ai=${plannerAi}`);
      await copyClipboard(r.text);
      toast(`Đã sao chép lệnh tạo 14 brief cho AI ${plannerAi}.`);
    });
  }
  const loadPromptTemplates = useCallback(async () => {
    setPromptLoading(true);
    try {
      const result = await api<{ templates: PromptTemplates }>('/prompt-templates');
      setPromptTemplates(result.templates);
      setPromptDrafts(result.templates);
      setPromptPreview('');
    } catch (err) { toast(messageOf(err), 'error'); }
    finally { setPromptLoading(false); }
  }, []);
  // Loading persisted templates when entering this screen keeps the settings view current.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (tab === 'prompt-settings') void loadPromptTemplates(); }, [tab, loadPromptTemplates]);
  async function savePromptTemplate() {
    await execute(`prompt-save-${promptMode}`, async () => {
      const result = await api<{ mode: PromptMode; content: string }>(`/prompt-templates/${promptMode}`, {
        method: 'PUT', body: JSON.stringify({ content: promptDrafts[promptMode] }),
      });
      setPromptTemplates((current) => ({ ...current, [result.mode]: result.content }));
      setPromptDrafts((current) => ({ ...current, [result.mode]: result.content }));
      toast(`Đã lưu template ${result.mode.toUpperCase()}.`);
    });
  }
  async function deletePromptTemplate() {
    if (!window.confirm(`Xóa nội dung template ${promptMode.toUpperCase()}? Template sẽ trở về trạng thái chưa cấu hình.`)) return;
    await execute(`prompt-delete-${promptMode}`, async () => {
      await api(`/prompt-templates/${promptMode}`, { method: 'DELETE' });
      setPromptTemplates((current) => ({ ...current, [promptMode]: '' }));
      setPromptDrafts((current) => ({ ...current, [promptMode]: '' }));
      setPromptPreview('');
      toast(`Đã xóa template ${promptMode.toUpperCase()}.`);
    });
  }
  async function previewPromptTemplate() {
    const item = overview.items.find((candidate) => candidate.uid === promptPreviewUid) || overview.items[0];
    if (!item) return toast('Ngày này chưa có brief để xem trước.', 'info');
    await execute('prompt-preview', async () => {
      const result = await api<{ text: string }>('/prompt-templates/preview', {
        method: 'POST',
        body: JSON.stringify({ date, uid: item.uid, mode: promptMode, content: promptDrafts[promptMode] }),
      });
      setPromptPreview(result.text);
    });
  }
  function workspaceImageUrl(item: Story): string {
    return `/api/workspace/image?date=${encodeURIComponent(date)}&ai=${item.ai}&slot=${laneSlot(item)}`;
  }
  function archiveImageUrl(item: Story & { date: string }): string {
    return `/api/workspace/image?date=${encodeURIComponent(item.date)}&ai=${item.ai}&slot=${laneSlot(item)}`;
  }
  async function openArchiveViewer(item: Story & { date: string }) {
    await execute(`archive-view-${item.uid}`, async () => {
      const outputPromise = api<WorkspaceFile>(
        `/workspace/file?date=${encodeURIComponent(item.date)}&ai=${item.ai}&slot=${laneSlot(item)}&kind=output`,
      );
      const imageUrl = archiveImageUrl(item);
      const imagePromise = fetch(imageUrl, { cache: 'no-store' });
      const [outputResult, imageResult] = await Promise.allSettled([outputPromise, imagePromise]);
      const output = outputResult.status === 'fulfilled' ? outputResult.value : null;
      const imageExists = imageResult.status === 'fulfilled' && imageResult.value.ok;
      const imageWarning = imageExists ? undefined : 'Chưa có ảnh trả về trong workspace.';
      setArchiveViewer({ item, output, imageUrl, imageExists, imageWarning });
    });
  }
  async function copyReturnedImage(item: Story) {
    await execute(`copy-image-${item.uid}`, async () => {
      const response = await fetch(workspaceImageUrl(item), { cache: 'no-store' });
      if (!response.ok) throw new Error('Chưa có ảnh trả về hoặc ảnh không hợp lệ.');
      const blob = await response.blob();
      if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
        throw new Error('Trình duyệt không hỗ trợ sao chép ảnh trực tiếp. Hãy dùng Chrome hoặc Edge trên localhost/HTTPS.');
      }
      const sourceUrl = URL.createObjectURL(blob);
      try {
        const image = new window.Image();
        image.decoding = 'async';
        image.src = sourceUrl;
        await new Promise<void>((resolve, reject) => {
          image.onload = () => resolve();
          image.onerror = () => reject(new Error('Không thể giải mã ảnh trả về trong trình duyệt.'));
        });
        const canvas = document.createElement('canvas');
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        if (!canvas.width || !canvas.height) throw new Error('Ảnh trả về không có kích thước hợp lệ.');
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Trình duyệt không tạo được vùng xử lý ảnh.');
        context.drawImage(image, 0, 0);
        const pngBlob = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob((result) => result ? resolve(result) : reject(new Error('Không thể chuyển ảnh sang PNG.')), 'image/png');
        });
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob })]);
      } finally {
        URL.revokeObjectURL(sourceUrl);
      }
      toast(`Đã chép ảnh minh họa · ${item.title}`);
    });
  }
  async function saveReturnedImage(item: Story, itemDate = date) {
    await execute(`save-image-${item.uid}`, async () => {
      const path = `/workspace/image?date=${encodeURIComponent(itemDate)}&ai=${item.ai}&slot=${laneSlot(item)}`;
      const response = await fetch('/api' + path, { cache: 'no-store' });
      if (!response.ok) throw new Error('Chưa có ảnh trả về hoặc ảnh không hợp lệ.');
      const blob = await response.blob();
      const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png';
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${itemDate}_AI${item.ai}_${String(laneSlot(item)).padStart(2, '0')}_image.${extension}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast(`Đã lưu ảnh minh họa · ${item.title}`);
    });
  }
  async function exportLane(ai: 1 | 2 | 3) {
    await execute(`export-${ai}`, async () => {
      const result = await api<{ written: number; skipped: number; folder: string; prompt_files?: number }>('/workspace/export-with-image',
        { method: 'POST', body: JSON.stringify({ date, ai }) });
      await refreshWorkspace();
      toast(`AI ${ai}: đã xuất ${result.written} file TXT${result.skipped ? `, bỏ qua ${result.skipped} slot đã tồn tại` : ''}.`);
    });
  }
  async function openWorkspaceConfig() {
    await execute('workspace-config-read', async () => {
      const result = await api<WorkspaceConfig>('/workspace/config');
      setWorkspaceConfig(result);
      setConfigFolder(result.folder);
      setConfigOpen(true);
    });
  }
  async function saveWorkspaceConfig() {
    await execute('workspace-config-save', async () => {
      const result = await api<WorkspaceConfig>('/workspace/config', {
        method: 'PUT', body: JSON.stringify({ folder: configFolder }),
      });
      setWorkspaceConfig(result);
      setConfigFolder(result.folder);
      setConfigOpen(false);
      setWorkspaceStatus({});
      await refreshWorkspace();
      toast(`Đã đổi workspace: ${result.folder}`);
    });
  }
  async function openWorkspaceFile(item: Story, kind: 'prompt' | 'image_prompt' | 'output') {
    const status = workspaceStatus[item.ai]?.find((entry) => entry.slot === laneSlot(item));
    try {
      const result = await api<WorkspaceFile>(`/workspace/file?date=${date}&ai=${item.ai}&slot=${laneSlot(item)}&kind=${kind}`);
      setFileViewer({ item, kind, content: result.content, hash: result.hash, filename: result.filename, exists: result.exists, warning: result.warning });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) {
        setFileViewer({
          item, kind, content: '', hash: null,
          filename: kind === 'prompt' ? (status?.prompt_filename || '') :
            kind === 'image_prompt' ? (status?.image_prompt_filename || '') : (status?.output_filename || ''),
          exists: false, warning: err.status === 409 ? err.message : undefined,
        });
        return;
      }
      toast(messageOf(err), 'error');
    }
  }
  async function saveWorkspaceFile() {
    if (!fileViewer || !fileViewer.exists) return;
    await execute('workspace-file-save', async () => {
      const slot = laneSlot(fileViewer.item);
      await api('/workspace/file', {
        method: 'PUT',
        body: JSON.stringify({
          date, ai: fileViewer.item.ai, slot, kind: fileViewer.kind,
          content: fileViewer.content, expected_hash: fileViewer.hash,
        }),
      });
      const result = await api<WorkspaceFile>(`/workspace/file?date=${date}&ai=${fileViewer.item.ai}&slot=${slot}&kind=${fileViewer.kind}`);
      setFileViewer({ ...fileViewer, content: result.content, hash: result.hash, filename: result.filename, exists: result.exists });
      await refreshWorkspace();
      toast('Đã lưu file TXT.');
    });
  }
  async function deleteWorkspaceFile() {
    if (!fileViewer || !fileViewer.exists || !window.confirm(`Xóa file ${fileViewer.filename}? Brief trong SQLite sẽ không bị xóa.`)) return;
    await execute('workspace-file-delete', async () => {
      const slot = laneSlot(fileViewer.item);
      await api(`/workspace/file?date=${date}&ai=${fileViewer.item.ai}&slot=${slot}&kind=${fileViewer.kind}`, { method: 'DELETE' });
      setFileViewer({ ...fileViewer, content: '', hash: null, exists: false });
      await refreshWorkspace();
      toast('Đã xóa file TXT.');
    });
  }
  function downloadWorkspaceFile() {
    if (!fileViewer?.exists) return;
    const blob = new Blob([fileViewer.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileViewer.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  async function importIdeas() {
    await execute('plan-import', async () => {
      const oldLane = overview.items.filter((x) => x.ai === plannerAi);
      if (oldLane.some((x) => x.status !== 'ready')) {
        toast(`AI ${plannerAi} đã có thẻ được giao; không thể ghi đè.`, 'error'); return;
      }
      let replaceReady = false;
      if (oldLane.length) {
        if (!window.confirm(`Thay thế ${oldLane.length} thẻ CHƯA GIAO của AI ${plannerAi} vào ngày ${date}?`)) return;
        replaceReady = true;
      }
      let allowSimilar = false;
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const result = await api<{ message: string }>(`/days/${date}/plan`, { method: 'POST',
            body: JSON.stringify({ ai: plannerAi, text: plannerText, replace_ready: replaceReady, allow_similar: allowSimilar }) });
          setPlannerText('');
          await refresh(date, false);
          toast(result.message);
          return;
        } catch (err) {
          const detail = err instanceof ApiError ? err.detail as PlanConflict : undefined;
          if (err instanceof ApiError && err.status === 409 && detail?.code === 'similar_ideas' && !allowSimilar) {
            const warnings = (detail.alerts || []).map((x) => `${x.line}. ${x.title} ↔ ${x.other_title} (${Math.round(x.score * 100)}%)`).join('\n');
            if (!window.confirm(`Cảnh báo trùng từ khóa:\n${warnings}\n\nVẫn nhập 14 ý tưởng?`)) return;
            allowSimilar = true; continue;
          }
          throw err;
        }
      }
    });
  }

  async function restoreBackup(file: File | undefined) {
    if (!file) return;
    if (!window.confirm('Khôi phục JSON sẽ GHI ĐÈ toàn bộ dữ liệu hiện tại. Bạn nên tải bản sao lưu trước. Tiếp tục?')) {
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    await execute('restore', async () => {
      if (file.size > 12_000_000) throw new Error('File lớn hơn 12 MB.');
      const raw = await file.text();
      await api('/restore', { method: 'POST', body: raw });
      await refresh(date, false);
      await refreshHistory();
      setUnavailable('');
      toast('Khôi phục dữ liệu thành công.');
    });
    if (fileRef.current) fileRef.current.value = '';
  }

  const visibleItems = useMemo(() => overview.items.filter((item) => {
    const q = search.trim().toLowerCase();
    if (q && !`${item.title} ${item.conflict} ${item.hero} ${item.theme} ${item.slot}`.toLowerCase().includes(q)) return false;
    if (filter === 'ready') return item.status === 'ready';
    if (filter === 'active') return item.status === 'sent' || item.status === 'part1';
    if (filter === 'done') return item.status === 'done';
    return true;
  }), [overview.items, search, filter]);
  const plannedLines = plannerText.split('\n').filter((line) => line.includes('||')).length;
  const progressPercent = overview.stats.total ? Math.round(overview.stats.done * 100 / overview.stats.total) : 0;

  const navItems: { id: Tab; title: string; desc: string; icon: typeof LayoutDashboard }[] = [
    { id: 'dashboard', title: 'Trang chủ', desc: 'Tổng quan hệ thống', icon: LayoutDashboard },
    { id: 'vault', title: 'Kho ý tưởng', desc: '42 brief theo ngày', icon: Database },
    { id: 'archive', title: 'Kho lưu trữ', desc: 'Bài đã hoàn tất', icon: CloudDownload },
    { id: 'workflow', title: 'Workflow', desc: 'Hàng đợi sản xuất', icon: Layers },
    { id: 'planner', title: 'Bổ sung ý tưởng', desc: '14 brief / AI', icon: WandSparkles },
    { id: 'history', title: 'Lịch sử & sao lưu', desc: 'Dữ liệu an toàn', icon: History },
    { id: 'prompt-settings', title: 'Cài đặt Prompt', desc: 'Template Full / P1 / P2', icon: Settings2 },
  ];

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-overlay" aria-label="Đóng menu" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand"><div className="brand-icon"><BookOpen size={24} strokeWidth={2.5} /></div>
          <div><div className="brand-title">THẮNG MIA</div><div className="brand-sub">WEB STUDIO <span className="brand-dot">•</span> V3.0</div></div>
        </div>
        <div className="sidebar-section-label">MENU</div>
        <nav className="nav-list" aria-label="Điều hướng chính">
          {navItems.map(({id, title, desc, icon: Icon}) => (
            <button key={id} onClick={() => { setTab(id); if (id === 'vault') setFilter('all'); setSidebarOpen(false); }} className={`nav-link ${tab === id ? 'active' : ''}`}>
              <Icon size={20}/><span className="nav-text"><strong>{title}</strong><small>{desc}</small></span>
              {tab === id && <span className="nav-active-dot"/>}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-area">
        <div className="workspace">
          {unavailable && <div className="warning-banner"><AlertCircle size={20}/><div><strong>Chưa thể tạo đủ 42 ý tưởng cho ngày này.</strong><span>{unavailable} — chuyển sang tab Bổ sung ý tưởng để nhập 14 brief cho từng AI.</span></div><button onClick={() => setTab('planner')}>Bổ sung <ArrowRight size={15}/></button></div>}

          {tab === 'dashboard' && <>
            <section className="dashboard-overview">
              <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> STORY PRODUCTION COMMAND CENTER</div>
                <h1>Trang <span>chủ</span></h1>
                <p>Tổng quan tiến độ 42 brief mỗi ngày qua 3 AI.</p>
              </div><div className="view-controls"><div className="date-control"><CalendarDays size={17}/><input aria-label="Ngày làm việc" type="date" value={date} onChange={(e) => { if (e.target.value) setDate(e.target.value); }}/></div>
                <button className="icon-button" aria-label="Làm mới dữ liệu" title="Làm mới" onClick={() => void refresh(date, false)}><RefreshCw size={18}/></button></div></div>

              <div className="stats-grid">
                <div className="stat-card"><div className="stat-top"><span>TỔNG THẺ Ý TƯỞNG</span><div className="stat-icon blue"><Layers size={19}/></div></div><div className="stat-number">{overview.stats.total}<span> / 42</span></div><div className="stat-foot"><span className="stat-spark">✦</span> 14 nhóm chủ đề / ngày</div></div>
                <div className="stat-card"><div className="stat-top"><span>ĐÃ HOÀN TẤT</span><div className="stat-icon green"><CheckCircle2 size={19}/></div></div><div className="stat-number">{overview.stats.done}<span> truyện</span></div><div className="mini-progress"><div style={{width: `${progressPercent}%`}} /></div><div className="stat-foot">{progressPercent}% tiến độ trong ngày</div></div>
                <div className="stat-card"><div className="stat-top"><span>ĐANG XỬ LÝ</span><div className="stat-icon orange"><Activity size={19}/></div></div><div className="stat-number">{overview.stats.in_progress}<span> truyện</span></div><div className="stat-foot"><span className="stat-spark orange-text">↗</span> Đã sao chép prompt</div></div>
                <div className="stat-card"><div className="stat-top"><span>CHƯA GIAO</span><div className="stat-icon purple"><Clipboard size={19}/></div></div><div className="stat-number">{overview.stats.ready}<span> truyện</span></div><div className="stat-foot">Đang chờ gửi tới AI</div></div>
              </div>
            </section>
            <div className="home-info-grid">
              <section className="panel system-info"><div className="panel-step-label">THÔNG TIN HỆ THỐNG</div>
                <div className="system-info-row"><span><Database size={16}/> Kho ý tưởng</span><strong>{overview.library_size}</strong></div>
                <div className="system-info-row"><span><Layers size={16}/> Ngày làm việc</span><strong>{overview.days_count}</strong></div>
                <div className="system-info-row"><span><Zap size={16}/> Kết nối AI</span><strong className="tiny-pill">Thủ công</strong></div>
              </section>
              <section className="panel privacy-card"><div className="privacy-head"><ShieldCheck size={20}/><strong>Riêng tư & kiểm soát</strong></div>
                <p>Không gọi API AI. Không lưu truyện hoàn chỉnh. Dữ liệu được giữ trong backend của bạn.</p>
                <span className="system-online"><span/> Hệ thống web nội bộ</span>
              </section>
            </div>

          </>}

          {tab === 'vault' && <>
            <section className="workflow-section vault-page">
              <div className="section-heading"><div><div className="eyebrow muted">IDEA VAULT</div><h2>Kho ý tưởng <span className="num-badge">{overview.items.filter((item) => item.status !== 'done').length} bài còn lại</span> <span className="num-badge">{overview.stats.done} đã hoàn tất</span></h2><p>Xem, tìm kiếm và chỉnh sửa brief chưa hoàn tất. Bài đã hoàn tất được giữ trong Workflow và Lịch sử nhưng tự ẩn khỏi kho.</p></div>
                <div className="view-controls"><div className="date-control"><CalendarDays size={17}/><input aria-label="Ngày kho ý tưởng" type="date" value={date} onChange={(e) => { if (e.target.value) setDate(e.target.value); }}/></div><button className="icon-button" aria-label="Làm mới kho ý tưởng" onClick={() => void refresh(date, false)}><RefreshCw size={18}/></button></div></div>
              <div className="filter-row"><div className="search-box"><Search size={17}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm trong 7 trường brief..." aria-label="Tìm ý tưởng" />{search && <button aria-label="Xóa tìm kiếm" onClick={() => setSearch('')}><X size={14}/></button>}</div>
                <div className="filter-pills"><Filter size={16}/>{([['all','Tất cả'],['ready','Chưa giao'],['active','Đang xử lý']] as const).map(([key,label]) => <button key={key} onClick={() => setFilter(key)} className={filter === key ? 'selected':''}>{label}</button>)}</div>
                <select className="vault-sort" value={vaultSort} onChange={(e) => setVaultSort(e.target.value as typeof vaultSort)}><option value="slot">Sắp xếp vị trí</option><option value="title">Sắp xếp tiêu đề</option><option value="status">Sắp xếp trạng thái</option></select></div>
              <div className="vault-grid">{([1,2,3] as const).map((ai) => {
                const items = visibleItems.filter((item) => item.ai === ai && item.status !== 'done').sort((a, b) =>
                  vaultSort === 'title' ? a.title.localeCompare(b.title) :
                  vaultSort === 'status' ? a.status.localeCompare(b.status) : a.slot - b.slot);
                return <section className={`vault-lane ${vaultCollapsed[ai] ? 'collapsed' : ''}`} key={ai}><div className="vault-lane-head"><strong>AI {ai}</strong><span>{items.length} / 14</span><button type="button" className="small-button vault-collapse" onClick={() => setVaultCollapsed((current) => ({ ...current, [ai]: !current[ai] }))}>{vaultCollapsed[ai] ? 'Mở rộng' : 'Thu gọn'}</button></div>
                  <div className="vault-lane-cards">{items.map((item) => {
                    const fileStatus = workspaceStatus[ai]?.find((entry) => entry.slot === laneSlot(item));
                    return <article className="vault-card" key={item.uid}>
                      <div className="card-meta"><span className="card-index">#{String(laneSlot(item)).padStart(2, '0')}</span><span>{overview.theme_names[item.theme] || item.theme}</span><span className={`status-pill ${item.status}`}>{STATUSES[item.status]}</span></div>
                      <h3>{item.title}</h3>
                      <div className="vault-fields">{FIELD_LABELS.map(({key, label}) => <div key={key}><b>{label}</b><span>{item[key]}</span></div>)}</div>
                      <div className="vault-meta-actions"><button className={`small-button ${item.favorite ? 'favorite-active' : ''}`} onClick={() => void updateMetadata(item, { favorite: !item.favorite })}>★ {item.favorite ? 'Đã thích' : 'Yêu thích'}</button><button className="small-button" onClick={() => void updateMetadata(item, { draft: !item.draft })}>{item.draft ? 'Bản nháp' : 'Đánh dấu nháp'}</button><button className="small-button" onClick={() => openEditor(item)}><Pencil size={14}/> Sửa</button><button className="small-button vault-delete" onClick={() => void deleteIdea(item)} disabled={!!working}><X size={14}/> Xóa bài</button></div>
                      <textarea className="vault-notes" value={item.notes || ''} onChange={(e) => setOverview((current) => ({ ...current, items: current.items.map((candidate) => candidate.uid === item.uid ? { ...candidate, notes: e.target.value } : candidate) }))} onBlur={(e) => void updateMetadata(item, { notes: e.target.value })} placeholder="Ghi chú riêng..." rows={2}/>
                      {fileStatus?.prompt_exists || fileStatus?.output_exists ? <div className="vault-warning"><AlertCircle size={14}/> Đã có file TXT/output; chỉnh sửa không tự xóa hoặc ghi đè file cũ.</div> : null}
                    </article>;
                  })}</div>
                </section>;
              })}</div>
            </section>
          </>}

          {tab === 'archive' && <>
            <section className="workflow-section vault-page archive-page">
              <div className="section-heading"><div><div className="eyebrow muted">ARCHIVE</div><h2>Kho lưu trữ <span className="num-badge">{archivedItems.length} bài</span></h2><p>Bài hoàn tất được chuyển vào đây khi bấm Bài tiếp theo và tự xóa sau 2 ngày.</p></div>
                <button className="icon-button" aria-label="Làm mới kho lưu trữ" onClick={() => void api<{ items: (Story & { date: string })[] }>('/archive').then((result) => setArchivedItems(result.items)).catch((err) => toast(messageOf(err), 'error'))}><RefreshCw size={18}/></button></div>
              <div className="vault-grid archive-grid">{archivedItems.length ? archivedItems.map((item) =>
                <article className="vault-card archive-card" key={`${item.date}-${item.uid}`}>
                  <div className="card-meta"><span>{prettyDate(item.date)}</span><span className="card-index">AI {item.ai} · #{String(laneSlot(item)).padStart(2, '0')}</span><span className="status-pill done">Đã lưu trữ</span></div>
                  <h3>{item.title}</h3>
                  <p className="card-conflict">{item.conflict}</p>
                  <button type="button" className="small-button" onClick={() => void openArchiveViewer(item)}><FileText size={14}/> Xem bài</button>
                  <small>Tự xóa sau 2 ngày kể từ {item.archived_at ? new Date(item.archived_at).toLocaleString('vi-VN') : ''}</small>
                </article>
              ) : <div className="lane-empty"><Database size={28}/><strong>Kho lưu trữ đang trống</strong><span>Các bài hoàn tất sẽ xuất hiện khi chuyển sang bài tiếp theo.</span></div>}</div>
            </section>
          </>}

          {tab === 'prompt-settings' && <>
            <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> PROMPT TEMPLATE SETTINGS</div><h1>Cài đặt <span>Prompt</span></h1>            <p>Tự nhập và lưu độc lập bốn template. Ứng dụng không cung cấp prompt mặc định.</p></div>
              <button className="icon-button" aria-label="Tải lại template" title="Tải lại" onClick={() => void loadPromptTemplates()}><RefreshCw size={18}/></button></div>
            <section className="panel prompt-settings-panel">
              <div className="filter-pills">{(['full','part1','part2','image'] as PromptMode[]).map((mode) =>
                <button key={mode} className={promptMode === mode ? 'selected' : ''} onClick={() => { setPromptMode(mode); setPromptPreview(''); }}>{mode === 'full' ? 'Full' : mode === 'part1' ? 'Part 1' : mode === 'part2' ? 'Part 2' : 'Ảnh minh họa'}</button>)}</div>
              <p>Template hiện tại: {promptTemplates[promptMode].trim() ? 'Đã cấu hình' : 'Chưa cấu hình'}. Biến hợp lệ: <code>{'{{title}}'}</code>, <code>{'{{hero}}'}</code>, <code>{'{{antagonist}}'}</code>, <code>{'{{conflict}}'}</code>, <code>{'{{evidence}}'}</code>, <code>{'{{reversal}}'}</code>, <code>{'{{ending}}'}</code>.</p>
              {promptMode === 'image' && <p className="muted">Nên yêu cầu AI tạo ảnh dựa trên truyện vừa viết trong cùng hội thoại.</p>}
              <div className="view-controls"><label>Brief xem trước <select value={promptPreviewUid || overview.items[0]?.uid || ''} onChange={(e) => { setPromptPreviewUid(e.target.value); setPromptPreview(''); }}><option value="">Chưa có brief</option>{overview.items.map((item) => <option key={item.uid} value={item.uid}>AI {item.ai} · #{String(laneSlot(item)).padStart(2, '0')} · {item.title}</option>)}</select></label></div>
              <textarea className="plan-textarea" rows={12} value={promptDrafts[promptMode]} onChange={(e) => { setPromptDrafts((current) => ({ ...current, [promptMode]: e.target.value })); setPromptPreview(''); }} placeholder="Nhập toàn bộ câu lệnh tại đây..." spellCheck={false} />
              <div className="dialog-actions"><button className="button secondary" onClick={() => setPromptDrafts((current) => ({ ...current, [promptMode]: promptTemplates[promptMode] }))} disabled={promptDrafts[promptMode] === promptTemplates[promptMode]}><RotateCcw size={16}/> Hủy thay đổi</button><div className="dialog-right-actions"><button className="button secondary" onClick={() => void deletePromptTemplate()} disabled={!!working || !promptDrafts[promptMode]}><X size={16}/> Xóa mẫu</button><button className="button secondary" onClick={() => void previewPromptTemplate()} disabled={!!working || promptLoading}><Search size={16}/> Xem trước</button><button className="button primary" onClick={() => void savePromptTemplate()} disabled={!!working || promptDrafts[promptMode] === promptTemplates[promptMode]}><Check size={16}/> Lưu template</button></div></div>
              {promptPreview && <div className="panel"><div className="panel-step-label">XEM TRƯỚC · {prettyDate(date)} · BRIEF ĐẦU TIÊN</div><pre className="prompt-preview">{promptPreview}</pre></div>}
            </section>
          </>}

          {tab === 'workflow' && <>
            <section className="workflow-section workflow-page">
              <div className="section-heading"><div><div className="eyebrow muted">WORKFLOW</div><h2>Hàng đợi sản xuất <span className="num-badge">3 AI</span></h2><p>Chọn một lane để sao chép prompt tiếp theo và theo dõi các thẻ đang xử lý.</p></div>
                <div className="workflow-heading-actions"><div className="view-controls"><div className="date-control"><CalendarDays size={17}/><input aria-label="Ngày làm việc" type="date" value={date} onChange={(e) => { if (e.target.value) setDate(e.target.value); }}/></div>
                  <button className="icon-button" aria-label="Làm mới dữ liệu" title="Làm mới" onClick={() => void refresh(date, false)}><RefreshCw size={18}/></button></div>
                  <div className="section-actions"><button className="button secondary" onClick={() => void scanToday()} disabled={!!working}><Search size={16}/> Rà trùng ý tưởng</button>
                  <button className="button secondary" onClick={() => void openWorkspaceConfig()} disabled={!!working}><Database size={16}/> Workspace</button>
                  <button className="button secondary" onClick={() => void refreshWorkspace()} disabled={!!working}><RefreshCw size={16}/> Làm mới file</button>
                  <button className="button secondary" onClick={() => setFilter('ready')}><Layers size={16}/> Còn lại: {overview.ideas_remaining}</button></div></div></div>

              <div className="filter-row"><div className="search-box"><Search size={17}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm tên truyện, chủ đề, nhân vật..." aria-label="Tìm thẻ" />{search && <button aria-label="Xóa tìm kiếm" onClick={() => setSearch('')}><X size={14}/></button>}</div>
                <div className="filter-pills"><Filter size={16}/>{([['all','Tất cả'],['ready','Chưa giao'],['active','Đang xử lý'],['done','Hoàn tất']] as const).map(([key,label]) => <button key={key} onClick={() => setFilter(key)} className={filter === key ? 'selected':''}>{label}</button>)}</div></div>
              <div className="ai-grid">
              {([1,2,3] as const).map((ai) => {
                const lane = overview.items.filter(x => x.ai === ai);
                const visible = visibleItems.filter(x => x.ai === ai).sort((a, b) => laneSlot(a) - laneSlot(b));
                const cursor = visible.length ? laneCursors[ai] % visible.length : 0;
                const cardsToRender = laneViewAll[ai] ? visible : (visible[cursor] ? [visible[cursor]] : []);
                const returned = workspaceStatus[ai]?.filter((entry) => entry.output_exists).length ?? 0;
                const ready = lane.filter(x => x.status === 'ready').length;
                return <section key={ai} className="ai-lane">
                  <div className="lane-heading"><div className="lane-title-row"><div className={`ai-avatar avatar-${ai}`}><Sparkles size={19}/></div><div><h3>AI {ai}</h3><span>{returned} / {lane.length} đã trả về</span></div><div className="lane-count">{lane.length} THẺ</div></div>
                    <div className="lane-progress"><div style={{width: `${lane.length ? returned/lane.length*100 : 0}%`}}/></div>
                    <button type="button" className="button primary full" disabled={!ready || !!working} onClick={() => copyNext(ai)}><Clipboard size={16}/> Sao chép tiếp <ArrowRight size={17}/></button>
                    <button type="button" className="button secondary full" disabled={!!working} onClick={() => void exportLane(ai)}><FileText size={16}/> Xuất {lane.length * 2} prompt TXT</button>
                    <div className="lane-navigation">
                      <button type="button" className="small-button" disabled={!visible.length} onClick={() => void archiveDoneAndMove(ai, visible[cursor], cursor, visible.length)}><ChevronRight size={14}/> Bài tiếp theo</button>
                      <button type="button" className="small-button" disabled={!visible.length} onClick={() => setLaneViewAll((current) => ({ ...current, [ai]: !current[ai] }))}>{laneViewAll[ai] ? 'Thu gọn' : `Xem toàn bộ (${visible.length})`}</button>
                    </div>
                  </div>
                  <div className={`lane-cards ${laneViewAll[ai] ? 'show-all' : 'single-card'}`}>{cardsToRender.length ? cardsToRender.map((item) => {
                    const workspaceItem = workspaceStatus[ai]?.find((entry) => entry.slot === laneSlot(item));
                    const outputReturned = workspaceItem?.output_exists ?? false;
                    const imageReturned = workspaceItem?.image_exists ?? false;
                    return <article className={`story-card ${item.status === 'done' ? 'story-done' : ''} ${laneViewAll[ai] ? 'selectable-card' : ''}`} key={item.uid}
                    onClick={() => {
                      if (!laneViewAll[ai]) return;
                      const selectedIndex = visible.findIndex((visibleItem) => visibleItem.uid === item.uid);
                      setLaneCursors((current) => ({ ...current, [ai]: selectedIndex }));
                      setLaneViewAll((current) => ({ ...current, [ai]: false }));
                    }}
                    onKeyDown={(event) => {
                      if (!laneViewAll[ai] || (event.key !== 'Enter' && event.key !== ' ')) return;
                      event.preventDefault();
                      const selectedIndex = visible.findIndex((visibleItem) => visibleItem.uid === item.uid);
                      setLaneCursors((current) => ({ ...current, [ai]: selectedIndex }));
                      setLaneViewAll((current) => ({ ...current, [ai]: false }));
                    }}
                    tabIndex={laneViewAll[ai] ? 0 : undefined}
                    role={laneViewAll[ai] ? 'button' : undefined}>
                    <div className="card-meta"><span className="card-index">#{String(laneSlot(item)).padStart(2, '0')}</span><span className="meta-sep">·</span><span className="card-theme">{overview.theme_names[item.theme] || item.theme}</span></div>
                    <div className="story-title-row"><h4>{item.title}</h4><span className={`status-pill ${item.status}`}><span/>{STATUSES[item.status]}</span></div>
                    <p className="card-conflict">{item.conflict}</p>
                    <div className="story-card-actions" onClick={(event) => event.stopPropagation()}><button type="button" className="small-primary" disabled={!!working} onClick={() => void copyStory(item, 'full')}><Clipboard size={14}/> Sao chép</button>
                      {outputReturned && <button type="button" className="small-primary copy-output" disabled={!!working} onClick={() => void copyReturnedStory(item)}><Clipboard size={14}/> Sao chép truyện trả về</button>}
                      <button className="small-button" onClick={() => openEditor(item)}><Pencil size={14}/> Sửa / P1 / P2</button>
                      {item.status === 'sent' || item.status === 'part1' ? <button type="button" className="small-button copy-undo" title="Hoàn tác sao chép" aria-label="Hoàn tác sao chép" disabled={!!working} onClick={() => void undoCopied(item)}><RotateCcw size={14}/> Hoàn tác sao chép</button> : null}
                      <button type="button" className={`small-square ${outputReturned ? 'returned' : item.status === 'done' ? 'undo' : ''}`} title={outputReturned ? 'Extension đã trả về' : item.status === 'done' ? 'Hoàn tác trạng thái nghiệp vụ' : 'Đánh dấu hoàn tất nghiệp vụ'} aria-label={outputReturned ? 'Extension đã trả về' : item.status === 'done' ? 'Hoàn tác trạng thái nghiệp vụ' : 'Đánh dấu hoàn tất nghiệp vụ'} onClick={() => void toggleDone(item)}><Check size={16}/></button></div>
                    <div className="dialog-copy-hint"><span>TXT:</span>
                      <button type="button" onClick={() => void openWorkspaceFile(item, 'prompt')}>Prompt</button>
                      <button type="button" onClick={() => void openWorkspaceFile(item, 'image_prompt')}>Prompt ảnh</button>
                      <button type="button" onClick={() => void openWorkspaceFile(item, 'output')}>Truyện trả về</button>
                      {outputReturned && <small>Extension đã trả về · chưa đổi trạng thái nghiệp vụ</small>}
                    </div>
                    <div className="dialog-copy-hint image-result">
                      <span>Ảnh: {imageReturned ? 'Đã có ảnh' : workspaceItem?.warnings?.length ? 'Lỗi đọc ảnh' : 'Chưa có ảnh'}</span>
                      {imageReturned && <Image className="workflow-thumbnail" src={workspaceImageUrl(item)} alt={`Ảnh minh họa ${item.title}`} width={46} height={46} unoptimized />}
                      {imageReturned && <button type="button" onClick={() => window.open(workspaceImageUrl(item), '_blank', 'noopener,noreferrer')}>Xem ảnh</button>}
                      {imageReturned && <button type="button" onClick={() => void saveReturnedImage(item)}>Lưu ảnh</button>}
                      {imageReturned && <button type="button" onClick={() => void copyReturnedImage(item)}>Chép ảnh</button>}
                    </div>
                  </article>;
                  }) : <div className="lane-empty"><FileText size={28}/><strong>Không có thẻ phù hợp</strong><span>{lane.length ? 'Thử đổi bộ lọc hoặc từ khóa.' : 'Hãy bổ sung 14 ý tưởng cho AI này.'}</span></div>}</div>
                  <div className="lane-footer"><span><span className="mini-indicator"/> {ready} thẻ chưa giao</span><span>{lane.length} thẻ tổng</span></div>
                </section>;
              })}
              </div>
            </section>
          </>}

          {tab === 'planner' && <>
            <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> IDEA GENERATION</div><h1>Bổ sung <span>42 ý tưởng</span></h1><p>Tạo 14 brief mới cho mỗi AI, sau đó nhập lại kết quả dạng văn bản ngắn.</p></div><div className="view-controls"><div className="date-control"><CalendarDays size={17}/><input aria-label="Ngày làm việc" type="date" value={date} onChange={(e) => { if (e.target.value) setDate(e.target.value); }}/></div><button className="icon-button" aria-label="Làm mới dữ liệu" title="Làm mới" onClick={() => void refresh(date, false)}><RefreshCw size={18}/></button></div></div>
            <div className="planner-grid"><section className="panel planner-step"><div className="panel-step-label">BƯỚC 01 <span>CHỌN LUỒNG AI</span></div>
              <h2>Chọn AI cần bổ sung</h2><p>Mỗi AI tạo đúng 14 brief theo thứ tự 14 nhóm chủ đề.</p>
              <div className="ai-picker">{([1,2,3] as const).map(ai => <button key={ai} className={plannerAi === ai ? 'picked' : ''} onClick={() => setPlannerAi(ai)}><div className={`ai-avatar avatar-${ai}`}><Sparkles size={17}/></div><strong>AI {ai}</strong><small>{overview.items.filter(x => x.ai === ai).length}/14 thẻ</small>{plannerAi === ai && <CheckCircle2 size={17} className="picker-check"/>}</button>)}</div>
              <div className="step-divider"/><div className="panel-step-label">BƯỚC 02 <span>TẠO PROMPT Ý TƯỞNG</span></div>
              <h2>Sao chép lệnh lập kế hoạch</h2><p>Gửi prompt này vào giao diện AI mà bạn đang dùng. AI sẽ trả về đúng 14 dòng theo định dạng yêu cầu.</p>
              <button className="button primary full big" onClick={() => void copyPlanningPrompt()} disabled={!!working}><Clipboard size={17}/> Sao chép lệnh tạo 14 ý tưởng <ArrowRight size={17}/></button>
              <div className="info-note"><CircleHelp size={18}/><span>Ứng dụng chỉ lưu brief ngắn, không yêu cầu dán lại toàn bộ truyện hoàn chỉnh.</span></div>
            </section>
            <section className="panel planner-input"><div className="panel-step-label">BƯỚC 03 <span>NHẬP KẾT QUẢ TỪ AI {plannerAi}</span></div>
              <div className="planner-input-head"><div><h2>Dán 14 dòng brief</h2><p>1 dòng = 1 ý tưởng, gồm 8 cột cách nhau bởi <code> || </code>.</p></div><span className={`line-counter ${plannedLines === 14 ? 'counter-valid' : ''}`}>{plannedLines} / 14 dòng</span></div>
              <div className="format-preview"><span>ĐỊNH DẠNG MẪU</span><code>01 || TITLE || PROTAGONIST || ANTAGONIST || UNFAIR ACTION || EVIDENCE || REVERSAL || ENDING</code></div>
              <textarea className="plan-textarea" value={plannerText} onChange={(e) => setPlannerText(e.target.value)} spellCheck={false} placeholder={'01 || Title... || Main character... || Opponent... || Concrete injustice... || Verifiable evidence... || Reversal... || Resolution...\n02 || ...\n...\n14 || ...'} />
              <div className="textarea-foot"><span>Chỉ nhập ý tưởng, không nhập truyện 3.000 từ.</span><button className="button primary" disabled={!plannerText.trim() || !!working} onClick={() => void importIdeas()}><Plus size={17}/> Nhập 14 ý tưởng <ArrowRight size={16}/></button></div>
            </section></div>
          </>}

          {tab === 'history' && <>
            <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> DATA & BACKUP CENTER</div><h1>Lịch sử <span>& sao lưu</span></h1><p>Theo dõi tiến độ theo ngày và bảo vệ dữ liệu ý tưởng của bạn.</p></div><div className="view-controls"><div className="date-control"><CalendarDays size={17}/><input aria-label="Ngày làm việc" type="date" value={date} onChange={(e) => { if (e.target.value) setDate(e.target.value); }}/></div><button className="icon-button" aria-label="Làm mới dữ liệu" title="Làm mới" onClick={() => void refresh(date, false)}><RefreshCw size={18}/></button></div></div>
            <div className="history-summary"><div className="history-tile"><div className="stat-icon blue"><CalendarDays size={20}/></div><strong>{history?.days.length ?? overview.days_count}</strong><span>Ngày đã tạo</span></div><div className="history-tile"><div className="stat-icon purple"><Database size={20}/></div><strong>{history?.library_size ?? overview.library_size}</strong><span>Brief trong kho</span></div><div className="history-tile"><div className="stat-icon green"><BadgeCheck size={20}/></div><strong>{history?.starter_used ?? overview.starter_used}<small> / 84</small></strong><span>Seed mẫu đã sử dụng</span></div></div>
            <div className="history-grid"><section className="panel history-table-panel"><div className="panel-head"><div><h2>Lịch sử sản xuất</h2><p>Tình trạng các ngày làm việc đã lưu</p></div><button className="icon-button" onClick={() => void refreshHistory()} title="Làm mới"><RefreshCw size={18}/></button></div>
              <div className="table-scroll"><table className="data-table"><thead><tr><th>NGÀY LÀM VIỆC</th><th>SỐ THẺ</th><th>ĐÃ GIAO</th><th>HOÀN TẤT</th><th>TIẾN ĐỘ</th></tr></thead><tbody>{history?.days.map(day => <tr key={day.date}><td><button className="date-link" onClick={() => {setDate(day.date);setTab('dashboard');}}><CalendarDays size={15}/>{prettyDate(day.date)}</button></td><td>{day.count}</td><td>{day.assigned}</td><td><strong>{day.done}</strong></td><td><div className="table-progress"><div style={{width:`${day.count ? day.done/day.count*100 : 0}%`}} /></div></td></tr>)}{!history?.days.length && <tr><td colSpan={5} className="empty-table">Chưa có lịch sử ngày làm việc.</td></tr>}</tbody></table></div>
            </section><section className="panel backup-panel"><div className="panel-head"><div><h2>Sao lưu & khôi phục</h2><p>Dữ liệu JSON tương thích bản desktop</p></div><FileJson size={24} className="backup-icon"/></div>
              <div className="backup-option"><div className="backup-option-icon"><CloudDownload size={20}/></div><div><strong>Xuất bản sao JSON</strong><p>Tải toàn bộ thư viện, ngày và trạng thái</p></div><button className="small-button" onClick={() => void execute('backup', () => download('/backup','thangmia_backup.json'))}><Download size={15}/> Tải về</button></div>
              <div className="backup-option"><div className="backup-option-icon"><RotateCcw size={20}/></div><div><strong>Khôi phục bản sao</strong><p>Nhập file project.json từ bản desktop hoặc web</p></div><button className="small-button" onClick={() => fileRef.current?.click()}><FileJson size={15}/> Chọn file</button><input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={(e) => void restoreBackup(e.target.files?.[0])}/></div>
              <div className="danger-note"><AlertCircle size={17}/> Khôi phục sẽ ghi đè toàn bộ dữ liệu hiện có. Hãy tải bản sao trước.</div>
            </section></div>
          </>}
          <div className="page-footer"><span><ShieldCheck size={14}/> Offline-first · Không API AI · Không lưu toàn văn truyện</span>          <span>THẮNG MIA Web Studio v3.0.0</span></div>
        </div>
      </main>

      {editing && form && <div className="modal-backdrop" onMouseDown={(e) => {if(e.target === e.currentTarget){setEditing(null);setForm(null);}}}>
        <section className="dialog edit-dialog" role="dialog" aria-modal="true" aria-label="Chỉnh sửa brief"><div className="dialog-head"><div><div className="eyebrow muted">STORY BRIEF EDITOR · #{String(laneSlot(editing)).padStart(2,'0')}</div><h2>Chỉnh sửa cốt truyện</h2><p>{overview.theme_names[editing.theme]} · AI {editing.ai}</p></div><button className="icon-button" aria-label="Đóng" onClick={() => {setEditing(null);setForm(null);}}><X size={21}/></button></div>
          <div className="edit-fields">{FIELD_LABELS.map(({key,label,placeholder}) => <label key={key} className="edit-field"><span>{label}</span>{key === 'title' ? <input value={form[key]} onChange={e => setForm({...form,[key]:e.target.value})} placeholder={placeholder}/>:<textarea value={form[key]} onChange={e => setForm({...form,[key]:e.target.value})} placeholder={placeholder} rows={2}/>}</label>)}</div>
          <div className="dialog-actions"><button className="button subtle" onClick={() => void scanEdited()} disabled={!!working}><Search size={16}/> Kiểm tra gần giống</button><div className="dialog-right-actions"><button className="button secondary" disabled={!!working} onClick={() => {setEditing(null);setForm(null);}}>Hủy</button><button className="button primary" disabled={!!working} onClick={() => void saveEdit()}><Check size={16}/> Lưu & đóng</button></div></div>
          <div className="dialog-copy-hint"><span>Lưu thay đổi & sao chép prompt:</span><button onClick={() => void saveAndCopy('full')} disabled={!!working}>Full</button><button onClick={() => void saveAndCopy('part1')} disabled={!!working}>Part 1</button><button onClick={() => void saveAndCopy('part2')} disabled={!!working}>Part 2</button></div>
        </section></div>}
        {archiveViewer && <div className="modal-backdrop" onMouseDown={(e) => {if(e.target === e.currentTarget) setArchiveViewer(null);}}>
          <section className="dialog archive-view-dialog" role="dialog" aria-modal="true" aria-label="Xem bài lưu trữ">
            <div className="dialog-head"><div><div className="eyebrow muted">ARCHIVE · AI {archiveViewer.item.ai} · #{String(laneSlot(archiveViewer.item)).padStart(2, '0')}</div><h2>{archiveViewer.item.title}</h2><p>{prettyDate(archiveViewer.item.date)} · Bài đã hoàn tất</p></div><button className="icon-button" aria-label="Đóng" onClick={() => setArchiveViewer(null)}><X size={21}/></button></div>
            <div className="archive-view-fields">{FIELD_LABELS.map(({ key, label }) => <div key={key}><strong>{label}</strong><p>{archiveViewer.item[key]}</p></div>)}</div>
            <div className="archive-assets">
              <div className="archive-asset"><div className="archive-asset-heading"><FileText size={17}/><strong>Truyện trả về</strong></div>
                {archiveViewer.output?.exists ? <pre>{archiveViewer.output.content}</pre> : <p className="muted">{archiveViewer.output?.warning || 'Chưa có truyện trả về trong workspace.'}</p>}
              </div>
              <div className="archive-asset"><div className="archive-asset-heading"><ImageIcon size={17}/><strong>Ảnh trả về</strong></div>
                {archiveViewer.imageExists ? <Image className="archive-result-image" src={archiveViewer.imageUrl} alt={`Ảnh minh họa ${archiveViewer.item.title}`} width={640} height={420} unoptimized /> : <p className="muted">{archiveViewer.imageWarning}</p>}
                {archiveViewer.imageExists && <button type="button" className="small-button" onClick={() => void saveReturnedImage(archiveViewer.item, archiveViewer.item.date)}><Download size={14}/> Lưu ảnh</button>}
              </div>
            </div>
            <div className="dialog-actions"><button className="button primary" onClick={() => setArchiveViewer(null)}>Đóng</button></div>
          </section>
        </div>}
      {configOpen && workspaceConfig && <div className="modal-backdrop" onMouseDown={(e) => {if (e.target === e.currentTarget) setConfigOpen(false);}}>
        <section className="dialog edit-dialog" role="dialog" aria-modal="true" aria-label="Cấu hình workspace">
          <div className="dialog-head"><div><div className="eyebrow muted">WORKSPACE STORAGE</div><h2>Cấu hình thư mục TXT</h2><p>Backend xác nhận quyền đọc/ghi; trình duyệt không tự truy cập đường dẫn Windows.</p></div><button className="icon-button" aria-label="Đóng" onClick={() => setConfigOpen(false)}><X size={21}/></button></div>
          <label className="edit-field"><span>Đường dẫn tuyệt đối</span><input value={configFolder} onChange={(e) => setConfigFolder(e.target.value)} placeholder="D:\\ThangMiaData" /></label>
          <div className="info-note"><Database size={18}/><span>Hiện tại: {workspaceConfig.folder}<br/>Quyền workspace: {workspaceConfig.readable ? 'đọc được' : 'không đọc được'} · {workspaceConfig.writable ? 'ghi được' : 'không ghi được'}</span></div>
          <div className="dialog-actions"><button className="button secondary" onClick={() => void openWorkspaceConfig()} disabled={!!working}><RefreshCw size={16}/> Kiểm tra lại</button><div className="dialog-right-actions"><button className="button secondary" onClick={() => setConfigOpen(false)}>Hủy</button><button className="button primary" onClick={() => void saveWorkspaceConfig()} disabled={!!working}><Check size={16}/> Xác nhận thư mục</button></div></div>
        </section></div>}
      {fileViewer && <div className="modal-backdrop" onMouseDown={(e) => {if (e.target === e.currentTarget) setFileViewer(null);}}>
        <section className="dialog edit-dialog" role="dialog" aria-modal="true" aria-label={fileViewer.kind === 'output' ? 'Truyện trả về' : fileViewer.kind === 'image_prompt' ? 'Prompt ảnh' : 'Prompt TXT'}>
          <div className="dialog-head"><div><div className="eyebrow muted">{fileViewer.kind === 'output' ? 'GEMINI OUTPUT' : 'PROMPT TXT'}</div><h2>{fileViewer.kind === 'output' ? 'Truyện trả về' : fileViewer.kind === 'image_prompt' ? 'Prompt ảnh' : 'Prompt'}</h2><p>{fileViewer.filename || 'Chưa có file'} · AI {fileViewer.item.ai} · slot {String(laneSlot(fileViewer.item)).padStart(2, '0')}</p></div><button className="icon-button" aria-label="Đóng" onClick={() => setFileViewer(null)}><X size={21}/></button></div>
          {!fileViewer.exists ? <div className="report-empty"><FileText size={35}/><strong>{fileViewer.kind === 'output' ? 'Chưa có kết quả' : 'Chưa có prompt TXT'}</strong><p>{fileViewer.warning || 'File chưa tồn tại trong workspace hiện tại.'}</p></div> :
            <textarea className="plan-textarea" value={fileViewer.content} onChange={(e) => setFileViewer({ ...fileViewer, content: e.target.value })} spellCheck={false} rows={18} />}
          <div className="dialog-actions"><button className="button secondary" onClick={downloadWorkspaceFile} disabled={!fileViewer.exists}><Download size={16}/> Tải file</button><button className="button secondary" onClick={() => void deleteWorkspaceFile()} disabled={!fileViewer.exists || !!working}><RotateCcw size={16}/> Xóa file</button><div className="dialog-right-actions"><button className="button secondary" onClick={() => setFileViewer(null)}>Đóng</button><button className="button primary" onClick={() => void saveWorkspaceFile()} disabled={!fileViewer.exists || !!working}><Check size={16}/> Lưu file TXT</button></div></div>
        </section></div>}
      {report && <div className="modal-backdrop" onMouseDown={(e) => {if (e.target === e.currentTarget) setReport(null);}}><section className="dialog report-dialog" role="dialog" aria-modal="true" aria-label="Kết quả rà trùng"><div className="dialog-head"><div><div className="eyebrow muted">LEXICAL SIMILARITY CHECK</div><h2>{report.title}</h2><p>Phương pháp heuristic từ khóa, không phải kiểm tra đạo văn.</p></div><button className="icon-button" onClick={() => setReport(null)} aria-label="Đóng"><X size={20}/></button></div>
        <div className="report-list">{report.rows.length ? report.rows.map((r,i) => <div className="report-row" key={i}><span className="report-score">{Math.round(r.score*100)}%</span><div><strong>{r.left}</strong>{r.right && <p>↔ {r.right}</p>}</div></div>) : <div className="report-empty"><CheckCircle2 size={35}/><strong>Chưa phát hiện cặp gần giống</strong><p>Vẫn nên duyệt thủ công vì cách so từ khóa có thể bỏ sót ý tưởng giống nghĩa.</p></div>}</div><div className="dialog-actions"><button className="button primary" onClick={() => setReport(null)}>Đã hiểu</button></div></section></div>}
      {notice && <div className={`toast ${notice.type}`} role="status">{notice.type === 'error' ? <AlertCircle size={19}/> : notice.type === 'success' ? <CheckCircle2 size={19}/> : <CircleHelp size={19}/>}<span>{notice.text}</span><button onClick={() => setNotice(null)} aria-label="Đóng thông báo"><X size={16}/></button></div>}
      {loading && <div className="loading-indicator" title="Đang tải"><LoaderCircle size={19}/></div>}
    </div>
  );
}
