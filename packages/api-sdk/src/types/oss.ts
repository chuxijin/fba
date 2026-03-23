export interface OssUploadResult {
  url: string;
  object_key: string;
}

export interface OssUploadParams {
  path?: string;
  use_signed_url?: boolean;
  url_expire_seconds?: number;
  object_expire_days?: number;
}

