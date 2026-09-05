# 扫荡北航先锋-后端

## 本地测试环境

```bash
conda env create -f environment.yml
conda activate ros-buaa-backend
cp config.example.yaml config.yaml
# 在 config.yaml 中设置随机 DjangoSecretKey、OpenRouter 和 COS 凭据。
python manage.py migrate
python manage.py check
pytest -q
python manage.py runserver 127.0.0.1:8000
```

`config.yaml` 已被 Git 忽略。也可通过 `ROS_BUAA_CONFIG` 指定配置文件，
或通过 `DJANGO_SECRET_KEY`、`OPENROUTER_API_KEY`、`OPENROUTER_MODEL` 覆盖对应字段。
AI 请求使用 `https://openrouter.ai/api/v1`，默认模型为 `qwen/qwen3-vl-8b-instruct`，
支持文本和图片，单次调用超时默认 25 秒。图片存储使用腾讯云 COS。
自动测试替代外部 API，不消耗模型额度或写入真实存储桶。

ROS 测试环境及消息编译方法见相邻 `RosEnd` 仓库的 `environment.yml` 和 README。
本机需要代理时可先执行 `source /etc/profile.d/clash.sh`，再执行 `proxy_on`。

本项目是"扫荡北航前锋"机器人项目的后端服务器，基于 Django REST Framework 构建。它不仅为前端应用提供了功能丰富的 API 接口，更重要的是，它扮演着连接用户与 ROS (机器人操作系统) 的核心桥梁，实现了对机器人的远程状态监控、任务下发与精细控制。

## 主要功能

- JWT 用户认证: 通过 JSON Web Token (JWT) 实现安全、无状态的用户身份验证。
- ROS 连接管理: 动态管理与 `rosbridge` 的 WebSocket 连接，确保指令通道的稳定可靠。
- 机器人远程控制:
  - 键盘遥操作: 将用户的键盘输入实时转化为机器人的运动指令。
  - 机械臂控制: 提供独立的机械臂伸缩、升降和抓取控制接口。
- 地图与建图:
  - 远程建图: 通过 API 启动和停止机器人的 SLAM 建图程序。
  - 地图管理: 保存、查询和管理多张地图数据，地图图像文件储存于阿里云 OSS。
- 自主导航:
  - 航点管理: 在指定地图上创建、重命名和删除导航航点。
  - 自主巡逻: 下发巡逻任务，命令机器人按照预设航点路径进行自主移动。
  - 任务启停: 随时启动或中止当前的导航任务。
- 智能任务 (推断):
  - 自主抓取: 存在 `PICK_TRIGGER` 等指令，表明系统具备触发机器人检测并抓取特定目标（如垃圾）的能力。
  - 视觉识别: 集成了 OpenCV，并配置了人脸、烟火检测相关参数，推断具备相应的视觉识别能力。
- 大语言模型集成: 集成了 `qwen` (通义千问) API，推断用于自然语言理解、语音命令解析等高级交互功能。

## 核心技术与架构

### 技术栈

- 后端框架: Django & Django REST Framework
- ROS 通信: `roslibpy`
- 数据库: MySQL (生产环境), SQLite (开发环境)
- 身份认证: `djangorestframework-simplejwt`
- 云存储: 阿里云对象存储 (OSS)
- 图像处理: `OpenCV-Python`
- AI 集成: `openai` (兼容 Qwen 等模型)
- 配置文件: `PyYAML`

### 与 ROS 的通信机制

本后端的一大核心特性是它与 ROS 的通信方式。它**并非一个传统的 ROS 节点**，而是作为一个外部客户端，通过 WebSocket 协议与运行在机器人系统上的 **`rosbridge`** 服务进行交互。

- 连接方式: 后端采用 `roslibpy` 库，以单例模式 (`ROSClient`) 创建一个全局唯一的客户端，连接到 `config.yaml` 中指定的 ROS 主机和端口。
- 交互方式: 与 ROS 的数据交换主要通过**调用 ROS 服务 (Service)** 而非订阅话题 (Topic) 来完成。这种方式更适合执行请求/响应式的明确指令。
- 关键服务:
  - `/master_node`: 核心控制服务，几乎所有高级指令（如开始导航、启动建图）都通过调用此服务下发。
  - `/dynamic_map`: 用于获取栅格地图数据。
  - `/cur_pose`: 用于获取机器人当前的实时位姿。
- 工作流程: 后端API接收到来自前端的 HTTP 请求后，会根据业务逻辑构建一个符合 ROS 服务接口规范的请求体，然后通过 `roslibpy` 将其发送给对应的 ROS 服务，从而实现对机器人的控制。

## 开发指南

### 1. 环境准备

建议使用 `conda` 创建独立的 Python 环境，然后安装依赖：
```bash
conda env create -f environment.yml
conda activate ros-buaa-backend
```

### 2. 项目配置

项目的大部分关键配置（如数据库连接、ROS 地址、云存储密钥等）都储存在 `config.yaml` 文件中。

1.  项目根目录下**必须**包含一个名为 `config.yaml` 的文件。
2.  请参考 `config.yaml` 中的字段，填写您自己的配置信息。

```yaml
# 示例 config.yaml
Debug: true

# Mysql
DatabaseHost: 127.0.0.1
DatabasePort: 3306
# ... 其他数据库配置

# Object Storage (阿里云 OSS)
OSS_SECRET_ID: your_oss_id
# ... 其他OSS配置

# Ros
ROSHOST: 192.168.1.100 # 机器人ROS Master的IP地址
ROSPORT: 9090        # rosbridge的默认端口

# ... 其他配置
```

### 3. 运行项目

1.  数据库迁移: 首次运行前，请执行数据库迁移以创建必要的表结构。
    ```bash
    python manage.py migrate
    ```

2.  启动开发服务器:
    ```bash
    python manage.py runserver
    ```
    服务默认将在 `http://127.0.0.1:8000/` 启动。

## API 规范

- 身份认证: 除登录/注册等少数接口外，绝大多数 API 都需要 JWT 认证。请在请求的 `Authorization` 头中携带 `Bearer <Your-JWT-Token>`。
- API 前缀: 所有业务 API 均以 `/api/` 开头。
- 示例接口:
  - `POST /api/auth/login` - 用户登录
  - `GET /api/connect/check` - 检查与 ROS 的连接状态
  - `POST /api/map/create` - 创建地图
  - `POST /api/navigation/patrol` - 发起巡逻任务
  - `POST /api/user_ctrl/key_move` - 键盘遥操作

## 代码规范

- 模块化设计: 功能被清晰地划分到不同的 Django App (`se`) 和模块中 (`api`, `models`, `utils`)。
- 服务封装: 与 ROS、OSS 等外部服务的交互逻辑被分别封装在 `util_ros.py` 和 `util_oss.py` 中，便于维护和复用。
- 装饰器: 大量使用装饰器（如 `@require_jwt`, `@require_ros`）来处理鉴权、ROS 连接检查等横切关注点，保持视图函数整洁。
