import { api, setAuthTokens } from '../../lib/api';
import { TokenResponse } from '../../types';

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/api/v1/auth/login', { email, password });
    const tokens = res.data;
    setAuthTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },
};
