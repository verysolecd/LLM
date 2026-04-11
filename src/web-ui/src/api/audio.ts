import client from './client';

export const WhisperService = {
  getTools: () => client.get('/whisper/tools'),
  getModels: () => client.get('/whisper/models'),
  startTool: (toolName: string, model: string) => 
    client.post('/whisper/tool/start', { tool_name: toolName, model }),
  stopTool: (toolName: string) => 
    client.post('/whisper/tool/stop', null, { params: { tool_name: toolName } }),
  recognize: (data: { audio_path: string; model: string }) => client.post('/whisper/recognize', data)
};

export const TTSService = {
  getModels: () => client.get('/tts/models'),
  discoverModels: () => client.get('/tts/models/discover'),
  addModel: (model_dir: string) => client.post('/tts/models/add', null, { params: { model_dir } }),
  getStatus: (model_id?: string) => client.get('/tts/status', { params: { model_id } }),
  getVoices: () => client.get('/tts/voices'),
  saveVoice: (data: { name: string, source_path: string, ref_text?: string }) => client.post('/tts/save-voice', data),
  deleteVoice: (name: string) => client.delete(`/tts/voices/${name}`),
  getCustomVoices: () => client.get('/tts/custom_voices'),
  saveCustomVoice: (data: { temp_path: string; name: string; ref_text: string }) => client.post('/tts/custom_voices', data),
  deleteCustomVoice: (name: string) => client.delete(`/tts/custom_voices/${name}`),
  uploadRef: (blob: Blob, filename: string) => {
    const formData = new FormData();
    formData.append('file', blob, filename);
    return client.post('/tts/upload-ref', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  start: (model_id?: string) => client.post('/tts/start', null, { params: { model_id } }),
  stop: (model_id?: string) => client.post('/tts/stop', null, { params: { model_id } }),
  synthesize: (data: { 
    text: string; 
    model_id?: string; 
    voice?: string; 
    language?: string; 
    instruct?: string;
    ref_audio?: string;
    ref_text?: string;
  }) => client.post('/tts/synthesize', data),
  deleteSynthesis: (filename: string) => client.delete(`/tts/synthesis/${filename}`),
  getSynthesisHistory: () => client.get('/tts/synthesis-history'),
};
