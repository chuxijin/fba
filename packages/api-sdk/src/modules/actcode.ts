import type { ApiClient } from '../client/types';
import type {
  ActcodeOrderActivateResult,
  ActcodeOrderLoginResult,
  ActcodeOrderPayload,
  ActcodeOrderVerifyResult,
} from '../types/actcode';

export interface ActcodeModule {
  loginByAgisoOrder(data: ActcodeOrderPayload): Promise<ActcodeOrderLoginResult>;
  activateAgisoOrder(data: ActcodeOrderPayload): Promise<ActcodeOrderActivateResult>;
  verifyAgisoOrder(data: ActcodeOrderPayload): Promise<ActcodeOrderVerifyResult>;
}

export function createActcodeModule(client: ApiClient): ActcodeModule {
  return {
    loginByAgisoOrder(data) {
      return client.post<ActcodeOrderLoginResult>('/actcode/agiso/login', data);
    },
    activateAgisoOrder(data) {
      return client.post<ActcodeOrderActivateResult>('/actcode/agiso/activate', data);
    },
    verifyAgisoOrder(data) {
      return client.post<ActcodeOrderVerifyResult>('/actcode/agiso/verify', data);
    },
  };
}
