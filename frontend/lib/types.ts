export type Status = 'ready' | 'sent' | 'part1' | 'done';
export type Mode = 'full' | 'part1' | 'part2';
export type Tab = 'dashboard' | 'vault' | 'workflow' | 'planner' | 'history' | 'prompt-settings';
export type BriefFields = {
  title: string; hero: string; antagonist: string; conflict: string;
  evidence: string; reversal: string; ending: string;
};
export type Story = BriefFields & {
  id: string; uid: string; slot: number; lane_slot?: number; ai: 1 | 2 | 3;
  source: string; theme: string; status: Status; last_copied?: string; full_prompt?: string;
  notes?: string; favorite?: boolean; draft?: boolean;
};
export type Stats = { total: number; done: number; in_progress: number; ready: number; sent: number; part1: number };
export type Overview = {
  date: string; exists: boolean; items: Story[]; stats: Stats;
  theme_names: Record<string, string>; library_size: number; ideas_remaining: number;
  starter_used: number; starter_total: number; days_count: number;
};
export type HistoryDay = { date: string; count: number; assigned: number; done: number };
export type HistoryData = { days: HistoryDay[]; library_size: number; starter_used: number; starter_total: number };
export type Pair = { score: number; first: { slot: number; title: string }; second: { slot: number; title: string } };
export type Duplicate = { score: number; title: string; slot?: number };
export type PlanConflict = { code?: string; message?: string; alerts?: { line: number; score: number; title: string; other_title: string }[] };
export type WorkspaceLane = { path: string; exists: boolean; readable: boolean; writable: boolean };
export type WorkspaceConfig = { folder: string; exists: boolean; readable: boolean; writable: boolean; lanes: Record<string, WorkspaceLane> };
export type WorkspaceItem = {
  slot: number; uid: string; prompt_filename: string; output_filename: string;
  prompt_exists: boolean; output_exists: boolean; prompt_hash: string | null;
  output_hash: string | null; warnings: string[];
};
export type WorkspaceFile = { content: string; filename: string; hash: string | null; uid: string; exists: boolean; warning?: string };
export type PromptMode = 'full' | 'part1' | 'part2';
export type PromptTemplates = Record<PromptMode, string>;
