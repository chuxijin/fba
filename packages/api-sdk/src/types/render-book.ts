import type { PageData } from './common';

export type RenderBookMode = 'preview' | 'final';
export type RenderBookStatus = 'accepted' | 'running' | 'succeeded' | 'failed';
export type RenderBookKind = 'module' | 'wrong' | 'exam' | 'custom';
export type RenderContentMode = 'questions_only' | 'questions_with_answers';
export type RenderAnswerLayout = 'inline' | 'appendix';
export type RenderDeliveryMode = 'single_pdf' | 'split_pdf';
export type SolutionMode = 'none' | 'separate' | 'inline' | 'appendix';
export type RenderVariant = 'questions_only' | 'solutions_only' | 'combined_inline' | 'combined_appendix';
export type RenderFileKind = 'question_pdf' | 'solution_pdf' | 'combined_pdf';
export type RenderFileStatus = 'available' | 'failed';
export type RenderStorageType = 'local' | 'oss';

export type LayoutMode = 'compact' | 'standard' | 'loose' | 'single' | 'pad_landscape' | 'pad_portrait';
export type ThemeColor = 'blue' | 'green' | 'orange' | 'purple' | 'teal' | 'crimson' | 'indigo' | 'amber';

export interface RenderOptions {
  include_answer: boolean;
  include_analysis: boolean;
  layout_mode: LayoutMode;
  theme: ThemeColor;
  dark_mode: boolean;
  show_source: boolean;
}

export interface RenderOutputTargets {
  question_pdf: boolean;
  solution_pdf: boolean;
}

export interface RenderTemplateSummary {
  key: string;
  name: string;
  description: string;
  scene: string;
  subject?: null | string;
  estimated_latency: 'fast' | 'medium' | 'slow';
}

export interface RenderJobCreatePayload {
  template_key: string;
  mode?: RenderBookMode;
  title: string;
  subtitle?: null | string;
  subject?: null | string;
  book_kind?: null | RenderBookKind;
  content_mode?: null | RenderContentMode;
  answer_layout?: null | RenderAnswerLayout;
  delivery_mode?: null | RenderDeliveryMode;
  solution_mode?: null | SolutionMode;
  filters: Record<string, unknown>;
  options: RenderOptions;
  output_targets: RenderOutputTargets;
  metadata?: Record<string, unknown>;
}

export interface RenderTemplatePreviewRequest extends RenderJobCreatePayload {
  render_variant?: null | RenderVariant;
  layout_params?: Record<string, unknown>;
  upload_to_oss?: boolean;
}

export interface RenderJobFile {
  file_kind: RenderFileKind;
  render_variant?: null | RenderVariant;
  storage_type: RenderStorageType;
  status: RenderFileStatus;
  filename: string;
  content_type: string;
  size_bytes?: null | number;
  local_path?: null | string;
  object_key?: null | string;
  url?: null | string;
  error_message?: null | string;
  created_at: string;
  updated_at: string;
}

export interface RenderJobResult {
  job_id: string;
  status: RenderBookStatus;
  mode: RenderBookMode;
  template_key: string;
  title: string;
  subtitle?: null | string;
  subject?: null | string;
  book_kind?: null | RenderBookKind;
  content_mode?: null | RenderContentMode;
  answer_layout?: null | RenderAnswerLayout;
  delivery_mode?: null | RenderDeliveryMode;
  solution_mode?: null | SolutionMode;
  filters: Record<string, unknown>;
  options: RenderOptions;
  output_targets: RenderOutputTargets;
  render_variants: RenderVariant[];
  metadata: Record<string, unknown>;
  payload_path?: null | string;
  question_count?: null | number;
  material_count?: null | number;
  output_path?: null | string;
  error_message?: null | string;
  files: RenderJobFile[];
  created_at: string;
  updated_at: string;
}

export interface RenderTemplatePreviewResult {
  job: RenderJobResult;
  render_variant: RenderVariant;
  pdf_url?: null | string;
  payload: Record<string, unknown>;
  resolved_metadata: Record<string, unknown>;
}

export interface RenderJobListParams {
  job_id?: string;
  status?: RenderBookStatus;
  template_key?: string;
  mode?: RenderBookMode;
  user_id?: number;
  keyword?: string;
  page?: number;
  size?: number;
}

export type RenderJobPageData = PageData<RenderJobResult>;
