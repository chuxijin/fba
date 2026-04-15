import type { ApiClient } from '../client/types';
import type { PageData } from '../types/common';
import type {
  RenderFileKind,
  RenderJobCreatePayload,
  RenderJobListParams,
  RenderJobResult,
  RenderTemplatePreviewRequest,
  RenderTemplatePreviewResult,
  RenderTemplateSummary,
  RenderVariant,
} from '../types/render-book';

export interface RenderBookModule {
  listTemplates(): Promise<RenderTemplateSummary[]>;
  previewTemplate(data: RenderTemplatePreviewRequest): Promise<RenderTemplatePreviewResult>;
  createJob(data: RenderJobCreatePayload): Promise<RenderJobResult>;
  listJobs(params?: RenderJobListParams): Promise<PageData<RenderJobResult>>;
  getJob(jobId: string): Promise<RenderJobResult>;
  executeJob(jobId: string, uploadToOss?: boolean): Promise<RenderJobResult>;
  dispatchJob(jobId: string, uploadToOss?: boolean): Promise<RenderJobResult>;
  buildJobFileUrl(
    jobId: string,
    fileKind: RenderFileKind,
    options?: {
      inline?: boolean;
      prefer_url?: boolean;
      render_variant?: RenderVariant;
    },
  ): string;
  buildPreviewPdfUrl(
    jobId: string,
    options?: {
      prefer_url?: boolean;
      render_variant?: RenderVariant;
    },
  ): string;
}

function toQueryString(params: Record<string, string | undefined>) {
  const parts: string[] = [];
  Object.entries(params).forEach(([key, value]) => {
    if (!value) {
      return;
    }
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
  });
  const raw = parts.join('&');
  return raw ? `?${raw}` : '';
}

export function createRenderBookModule(client: ApiClient): RenderBookModule {
  return {
    listTemplates() {
      return client.get<RenderTemplateSummary[]>('/render-books/templates');
    },
    previewTemplate(data) {
      return client.post<RenderTemplatePreviewResult>('/render-books/templates/preview', data);
    },
    createJob(data) {
      return client.post<RenderJobResult>('/render-books/jobs', data);
    },
    listJobs(params) {
      return client.get<PageData<RenderJobResult>>('/render-books/jobs', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    getJob(jobId) {
      return client.get<RenderJobResult>(`/render-books/jobs/${jobId}`);
    },
    executeJob(jobId, uploadToOss = true) {
      return client.post<RenderJobResult>(
        `/render-books/jobs/${jobId}/execute`,
        undefined,
        { params: { upload_to_oss: uploadToOss } },
      );
    },
    dispatchJob(jobId, uploadToOss = true) {
      return client.post<RenderJobResult>(
        `/render-books/jobs/${jobId}/dispatch`,
        undefined,
        { params: { upload_to_oss: uploadToOss } },
      );
    },
    buildJobFileUrl(jobId, fileKind, options) {
      const query = toQueryString({
        inline: options?.inline ? 'true' : undefined,
        prefer_url: options?.prefer_url ? 'true' : undefined,
        render_variant: options?.render_variant,
      });
      return `/render-books/jobs/${jobId}/files/${fileKind}${query}`;
    },
    buildPreviewPdfUrl(jobId, options) {
      const query = toQueryString({
        prefer_url: options?.prefer_url ? 'true' : undefined,
        render_variant: options?.render_variant,
      });
      return `/render-books/jobs/${jobId}/preview.pdf${query}`;
    },
  };
}
