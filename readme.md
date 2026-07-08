
<img src="assets/logo.jpg" alt="Clipsay — say it, clip it" width="720" />


# Clipsay — AI 视频创作工具

> **Say it, clip it.** 用 AI 将你的创意转化为惊艳的视频。

Clipsay 是一款 AI 驱动的视频创作桌面应用，支持从文案到成片的完整 AI 管道。输入一个创意想法，AI 自动完成故事生成、角色设计、肖像绘制、分镜设计、镜头帧生成、视频合成全流程。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Electron + React 18 + TypeScript |
| 构建 | electron-vite + Vite |
| 后端 | Python 3.13 + FastAPI |
| 数据库 | SQLite (aiosqlite) |
| AI 管道 | 7 步流水线，SSE 实时推送 |
| AI 供应商 | Agnes (Image / Video) |

## 快速开始

### 环境要求

- Node.js >= 18
- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) (Python 包管理器)

### 安装

```bash
# 克隆仓库
git clone <repo-url> && cd clipsay

# 安装前端依赖
npm install

# 安装后端依赖
cd backend
uv sync
cd ..
```

### 启动开发模式

```bash
npm run dev
```

这会同时启动：
- Vite 开发服务器 (renderer, 默认 `localhost:5173`)
- Electron 主进程 (自动启动 Python 后端)
- Python FastAPI 后端 (默认 `localhost:8765`)

### 构建

```bash
npm run build
```

## 项目结构

```
clipsay/
├── src/
│   ├── main/           # Electron 主进程
│   │   └── index.ts    # 窗口管理、后端进程、IPC
│   ├── preload/        # Electron preload script
│   └── renderer/       # React 前端
│       ├── App.tsx           # 主应用 (页面路由)
│       ├── NewProject.tsx    # 创作页面 (管道控制)
│       ├── Carousel.tsx      # 首页轮播
│       ├── CharacterCard.tsx # 角色造型卡片
│       ├── ShootingScriptCard.tsx # 拍摄脚本卡片
│       ├── PipelineControls.tsx  # 管道控制面板
│       ├── usePipelineSSE.ts # SSE 事件 hook
│       └── ...
├── backend/
│   ├── main.py         # FastAPI 入口
│   ├── api/            # REST API + SSE 端点
│   │   ├── routes.py   # 项目/角色/分镜 API
│   │   └── pipeline.py # 管道控制 + SSE 事件流
│   ├── pipeline/       # AI 管道核心
│   │   ├── runner.py         # 管道运行器
│   │   ├── step_registry.py  # 步骤注册表
│   │   ├── scene_storyboard.py # 分镜生成
│   │   ├── frame_generator.py  # 镜头帧生成
│   │   ├── events.py         # EventBus / SSE 事件
│   │   ├── conductor/        # 阶段协调器
│   │   ├── composite/        # 视频合成
│   │   └── steps/            # 各步骤实现
│   ├── services/       # AI 服务
│   │   ├── story_writer.py      # 故事生成
│   │   ├── character_generator.py # 角色提取
│   │   ├── portrait_generator.py  # 肖像生成
│   │   ├── storyboard_generator.py # 分镜设计
│   │   ├── reference_picker.py # 参考图选择
│   │   └── video_compositor.py   # 视频合成
│   ├── clients/        # AI API 客户端
│   │   ├── image.py    # 图片生成 (RateQueue)
│   │   ├── video.py    # 视频生成 (RateQueue)
│   │   ├── llm.py      # LLM 调用
│   │   ├── rate_limiter.py  # RPM/RPD 限流
│   │   └── providers/  # 供应商实现
│   ├── db/             # 数据库层
│   │   ├── _schema.py  # 表定义
│   │   ├── projects.py # 项目 CRUD
│   │   └── storyboards.py # 分镜数据
│   └── schemas/        # Pydantic 模型
│       ├── character.py
│       ├── camera.py
│       └── shot_spec.py
└── assets/             # 静态资源
```

## AI 管道流程

```
idea → story → characters → portraits → scene_scripts → storyboard → shot_frames → composite_video
```

| 步骤 | 说明 | 输入 | 输出 |
|------|------|------|------|
| `story` | 故事大纲生成 | 用户 idea | story_content |
| `characters` | 角色提取 | 故事 | 角色列表 + 外貌/服饰 |
| `portraits` | 角色肖像生成 | 角色描述 | front/side/back 三视图 |
| `scene_scripts` | 分场剧本 | 故事 + 角色 | 多场景剧本 |
| `storyboard` | 分镜设计 | 剧本 + 角色 | shot list + camera tree |
| `shot_frames` | 镜头帧 + 视频 | 分镜 + 肖像 | start/end frame + shot video |
| `composite_video` | 视频合成 | shot videos | composite.mp4 |

### 错误处理

- 每场景分镜失败自动重试 3 次（指数退避），耗尽后管道暂停
- 帧/视频生成失败自动重试 3 次，耗尽后管道暂停
- API 5xx 错误自动重试（ServerError → RateQueue 退避）
- 肖像 side/back 失败不影响 front，逐步降级

## API

| 端点 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /api/projects` | 项目列表 |
| `POST /api/projects` | 创建项目 |
| `GET /api/projects/{id}` | 项目详情 (含全量数据) |
| `PUT /api/projects/{id}` | 更新项目 |
| `POST /api/projects/{id}/duplicate` | 复制项目 |
| `GET /api/projects/{id}/pipeline/events` | SSE 事件流 |
| `POST /api/projects/{id}/pipeline/start` | 启动管道 |
| `POST /api/projects/{id}/pipeline/pause` | 暂停管道 |
| `POST /api/projects/{id}/pipeline/resume` | 恢复管道 |
| `POST /api/projects/{id}/pipeline/cancel` | 取消管道 |
| `POST /api/projects/{id}/pipeline/regenerate-step` | 重试单步 |
| `GET /api/projects/{id}/pipeline/status` | 管道状态 |

完整 API 文档：启动后端后访问 `http://localhost:8765/docs`

## SSE 事件协议

管道运行期间通过 SSE 实时推送状态：

| 事件类型 | 说明 |
|---------|------|
| `pipeline_started / completed / failed / paused` | 管道生命周期 |
| `step_start / complete / failed` | 步骤状态 |
| `emit_progress` | 进度更新 |
| `portrait_image_status` | 肖像生成状态 (逐角色/视角) |
| `storyboard_scene_ready` | 场景分镜完成 |
| `shot_frame_ready` | 镜头帧生成状态 (生成中/完成) |
| `shot_video_ready` | 镜头视频状态 (生成中/完成) |
| `scene_composite_ready` | 场景合成状态 (生成中/完成) |
| `final_video_ready` | 最终视频完成 |

## 许可证

MIT
