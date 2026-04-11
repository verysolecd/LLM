# 推理模型和语音合成模型管理

为推理模型和TTS语音模型（目前支持Qwen3-TTS）模型管理系统，支持多模型、跨模型兼容。

## 🌟 核心特性

- 🧠 推理模型加载和管理
- 🎤 Qwen3-TTS 语音合成
- 📥 ModelScope 模型下载
- 🔄 跨模型音色兼容
- ⏱️ 自定义超时设置
- 📝 合成历史管理
- 🎨 语音克隆功能

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
cd src/web-ui && npm install && npm run build
```

### 启动服务

```bash
python app.py &
cd src/web-ui && npm run dev
```

### 访问系统

打开浏览器访问 `http://localhost:8000`打开web管理页面

---

## 📁 项目结构

```
Qwen3-TTS/
├── .gitignore          # Git 忽略规则
├── app.py              # 后端入口
├── config.json         # 配置文件
├── requirements.txt    # Python 依赖
├── src/
│   ├── services/       # 后端服务
│   └── web-ui/         # 前端界面
├── _Models/            # 推理模型文件
├── tts_models/         # TTS 模型文件
└── tts_results/        # 合成结果
```

---

## 🎯 核心功能


### 🧠 推理模型加载与管理
支持多种模型格式，自动发现、加载和卸载，实时监控模型状态。

### 🎤 Qwen3-TTS 语音合成
支持 0.6B/1.7B 模型，跨模型兼容。

### 📥 ModelScope 模型下载
一键下载，自动格式转换，支持断点续传。

### 🔄 跨模型兼容
1.7B 模型音色可用于 0.6B 模型，自动降维。

### ⏱️ 自定义超时
灵活设置合成超时时间。

### 🎨 语音克隆
实时录音或上传音频克隆音色。

### 📝 合成历史
记录所有合成记录，支持播放/下载/删除。

### 🛠️ 模型管理
监控模型状态，支持启动/停止。

---

## 📝 使用说明

### 合成语音

1. 选择模型（0.6B 或 1.7B）
2. 输入文本
3. 选择音色
4. 点击"开始合成"按钮

### 管理音色

1. 录制语音或上传音频文件
2. 点击"保存音色"按钮
3. 输入音色名称
4. 保存后即可在音色列表中选择

---

## 🔧 配置文件

**config.json**:

```json
{
  "tts_models": [
    {
      "id": "faster-qwen3-tts",
      "name": "Qwen3-TTS Fast",
      "path": "tts_models/Qwen3-TTS-0.6B"
    },
    {
      "id": "qwen3-tts",
      "name": "Qwen3-TTS",
      "path": "tts_models/Qwen3-TTS-1.7B"
    }
  ]
}
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License