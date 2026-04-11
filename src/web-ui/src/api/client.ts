import axios from 'axios';

const client = axios.create({
  baseURL: `http://${window.location.hostname}:5001/api/v1`,
  timeout: 120000, // TTS 和 Llama 模型推理可能较慢，设置长超时
});

export default client;
