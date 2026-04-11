import client from './client';

export const LlamaService = {
  getModels: () => client.get('/models'),
  getStatus: () => client.get('/status'),
  start: (model: string) => client.post('/start', { model }),
  stop: (model: string) => client.post('/stop', null, { params: { model } }),
  chat: (data: { model: string; messages: any[]; stream?: boolean }) => 
    client.post('/chat', data),
};
