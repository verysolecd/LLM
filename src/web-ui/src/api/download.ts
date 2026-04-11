import client from './client';

export const DownloadService = {
  getStatus: () => client.get('/download/status'),
  download: (modelId: string, fileId?: string) => 
    client.post('/download/model', { model_id: modelId, file_id: fileId }),
};
