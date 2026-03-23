import type { ApiClient, FormDataLike } from '../client/types';
import type { OssUploadParams, OssUploadResult } from '../types/oss';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface OssModule {
  request: ScopedApiClient;
  upload(data: FormDataLike, params?: OssUploadParams): Promise<OssUploadResult>;
}

export function createOssModule(client: ApiClient): OssModule {
  const request = createScopedClient(client, '/oss');

  return {
    request,
    upload(data, params) {
      return request.post<OssUploadResult>('/upload', data, {
        params: params as Record<string, unknown> | undefined,
      });
    },
  };
}

