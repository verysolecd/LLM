import client from './client';

export const SystemService = {
  getLogs: (service: string) => client.get(`/logs/${service}`),
};
