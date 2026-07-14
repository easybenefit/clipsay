import { app, BrowserWindow, ipcMain, shell, Menu } from 'electron'
import { join, resolve } from 'path'
import { spawn, ChildProcess } from 'child_process'
import http from 'http'
import dayjs from 'dayjs'
import log from 'electron-log'

// 设置应用程序名称（macOS 菜单栏、Dock 等）
app.name = 'Clipsay'
const APP_NAME = app.name

// 显式设置应用菜单，覆盖 macOS 从 Info.plist 读取的 "Electron"
function setupAppMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: APP_NAME,
      submenu: [
        { role: 'about', label: `关于 ${APP_NAME}` },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide', label: `隐藏 ${APP_NAME}` },
        { role: 'hideOthers' },
        { type: 'separator' },
        { role: 'quit', label: `退出 ${APP_NAME}` }
      ]
    },
    {
      label: '文件',
      submenu: [
        { role: 'close', label: '关闭窗口' }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'forceReload', label: '强制重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' }
      ]
    },
    {
      label: '窗口',
      submenu: [
        { role: 'minimize', label: '最小化' },
        { role: 'zoom', label: '缩放' },
        { type: 'separator' },
        { role: 'front', label: '全部置于顶层' }
      ]
    },
    {
      label: '帮助',
      submenu: []
    }
  ]
  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

let splashWindow: BrowserWindow | null = null
let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

const PYTHON_PORT = 8765
const BACKEND_URL = `http://localhost:${PYTHON_PORT}`
const isDev = !app.isPackaged

// 用户专属数据目录(Electron 标准位置)
const USER_DATA = app.getPath('userData')
const APP_DATA = join(USER_DATA, 'app_data')
const PROJECT_DATA_ROOT = join(APP_DATA, 'data')
const LOCAL_ROOT = PROJECT_DATA_ROOT
const LOG_DIR = join(USER_DATA, 'logs')

// 确保目录存在
function ensureDir(p: string): void {
  try {
    require('fs').mkdirSync(p, { recursive: true })
  } catch (_) { /* 已存在即可 */ }
}
ensureDir(APP_DATA)
ensureDir(PROJECT_DATA_ROOT)
ensureDir(LOG_DIR)

// electron-log 写入主进程日志,按天分文件 + 单文件 10MB 轮转
log.transports.file.resolvePathFn = () =>
  join(LOG_DIR, `main-${dayjs().format('YYYY-MM-DD')}.log`)
log.transports.file.maxSize = 10 * 1024 * 1024
log.transports.file.format = '[{y}-{m}-{d} {h}:{i}:{s}] [{level}] {text}'
log.transports.console.level = isDev ? 'debug' : 'info'

// 后端进程环境:把业务路径注入 Python,使其写到 userData 下
const BACKEND_ENV = {
  ...process.env,
  CLIPSAY_DATA_ROOT: PROJECT_DATA_ROOT,
  CLIPSAY_DB_FILE: join(USER_DATA, 'clipsay.db'),
  CLIPSAY_LOCAL_DIR: LOCAL_ROOT,
  CLIPSAY_LOG_DIR: LOG_DIR,
}

function createSplashWindow(): void {
  splashWindow = new BrowserWindow({
    width: 720,
    height: 600,
    frame: false,
    transparent: true,
    resizable: false,
    center: true,
    show: false,
    skipTaskbar: true
  })

  const splashFile = resolve(__dirname, '../../src/splash/index.html')
  splashWindow.loadFile(splashFile)

  splashWindow.once('ready-to-show', () => {
    splashWindow?.show()
  })
}

function createMainWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    title: 'Clipsay',
    show: false,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#111118',
      symbolColor: '#ffffff',
      height: 36
    },
    webPreferences: {
      preload: resolve(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  if (isDev) {
    const devURL = process.env.ELECTRON_RENDERER_URL || 'http://localhost:5173'
    mainWindow.loadURL(devURL)
  } else {
    mainWindow.loadFile(resolve(__dirname, '../renderer/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    splashWindow?.close()
    splashWindow = null
    mainWindow?.show()
    // if (isDev) mainWindow?.webContents.openDevTools()
  })
}

function checkHealthOnce(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/health`, (res) => {
      let data = ''
      res.on('data', (chunk) => { data += chunk })
      res.on('end', () => resolve(res.statusCode === 200))
    })
    req.on('error', () => resolve(false))
    req.end()
  })
}

function pollHealth(timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const poll = async () => {
      if (await checkHealthOnce()) return resolve()
      if (Date.now() - start >= timeoutMs) return reject(new Error('Backend health check timed out'))
      setTimeout(poll, 1000)
    }
    poll()
  })
}

function spawnBackend(): ChildProcess {
  const projectRoot = resolve(__dirname, '..', '..')
  log.info(`[Main] Spawning backend from ${projectRoot}`)
  log.info(`[Main] CLIPSAY_DATA_ROOT=${PROJECT_DATA_ROOT}`)
  log.info(`[Main] CLIPSAY_DB_FILE=${join(USER_DATA, 'clipsay.db')}`)
  log.info(`[Main] CLIPSAY_LOG_DIR=${LOG_DIR}`)

  const proc = spawn('uv', ['run', 'uvicorn', 'backend.main:app', '--port', String(PYTHON_PORT)], {
    cwd: projectRoot,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: BACKEND_ENV
  })

  proc.stderr?.on('data', (data: Buffer) => {
    const text = data.toString().trim()
    if (text) log.info(`[Backend] ${text}`)
  })

  proc.stdout?.on('data', (data: Buffer) => {
    const text = data.toString().trim()
    if (text) log.info(`[Backend] ${text}`)
  })

  proc.on('close', (code: number | null) => {
    log.info(`[Main] Backend process exited with code ${code}`)
  })

  proc.on('error', (err) => {
    log.error(`[Main] Backend process error:`, err)
  })

  return proc
}

async function startPythonBackend(): Promise<void> {
  log.info(`[Main] Checking if backend is already running on port ${PYTHON_PORT}...`)

  const alreadyUp = await checkHealthOnce()
  if (alreadyUp) {
    log.info('[Main] Backend already running, connecting...')
    return
  }

  log.info('[Main] Starting backend...')
  pythonProcess = spawnBackend()

  try {
    await pollHealth(30000)
  } catch (err) {
    if (pythonProcess) {
      pythonProcess.kill()
      pythonProcess = null
    }
    throw err
  }
}

const MIN_SPLASH_MS = 2000

app.whenReady().then(async () => {
  setupAppMenu()
  createSplashWindow()
  const splashStart = Date.now()

  try {
    await startPythonBackend()
    const elapsed = Date.now() - splashStart
    if (elapsed < MIN_SPLASH_MS) {
      await new Promise(r => setTimeout(r, MIN_SPLASH_MS - elapsed))
    }
    createMainWindow()
    if (mainWindow) {
      mainWindow.on('maximize', () => mainWindow?.webContents.send('window-state-changed', { isMaximized: true }))
      mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window-state-changed', { isMaximized: false }))
      mainWindow.on('enter-full-screen', () => mainWindow?.webContents.send('window-state-changed', { isMaximized: true }))
      mainWindow.on('leave-full-screen', () => mainWindow?.webContents.send('window-state-changed', { isMaximized: false }))
    }
  } catch (err) {
    log.error('[Main] Failed to start backend:', err)
    setTimeout(() => {
      splashWindow?.close()
      app.quit()
    }, 2000)
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill()
    pythonProcess = null
  }
})

import Store from 'electron-store'

let store: Store | null = null

function getStore(): Store {
  if (!store) {
    store = new Store({
      name: 'clipsay-settings',
      encryptionKey: 'clipsay-enc-v1'
    })
  }
  return store
}

// ==================== IPC ====================

ipcMain.handle('get-backend-url', () => BACKEND_URL)

ipcMain.handle('get-settings', () => {
  try {
    return getStore().get('settings', {})
  } catch (e) {
    log.error('[Main] get-settings error:', e)
    return {}
  }
})

ipcMain.handle('save-settings', (_event, data) => {
  try {
    getStore().set('settings', data)
    return true
  } catch (e) {
    log.error('[Main] save-settings error:', e)
    return false
  }
})

// 存储配额扫描:仅统计业务产物根 app_data/data/
ipcMain.handle('storage:quota', async () => {
  const fs = require('fs') as typeof import('fs')
  const path = require('path') as typeof import('path')
  const DEFAULT_THRESHOLD = 2 * 1024 * 1024 * 1024 // 2GB
  const settings = (getStore().get('settings', {}) as { quotaThresholdBytes?: number })
  const threshold = settings.quotaThresholdBytes ?? DEFAULT_THRESHOLD

  let totalBytes = 0
  function walk(dir: string): void {
    let entries: import('fs').Dirent[]
    try { entries = fs.readdirSync(dir, { withFileTypes: true }) }
    catch { return }
    for (const e of entries) {
      const full = path.join(dir, e.name)
      try {
        if (e.isDirectory()) walk(full)
        else if (e.isFile()) {
          const st = fs.statSync(full)
          totalBytes += st.size
        }
      } catch (_) { /* 跳过权限异常 */ }
    }
  }
  walk(PROJECT_DATA_ROOT)

  return {
    totalBytes,
    threshold,
    exceeded: totalBytes > threshold,
    root: PROJECT_DATA_ROOT,
  }
})

// 在文件管理器中显示
ipcMain.handle('storage:reveal', (_event, fullPath: string) => {
  try {
    shell.showItemInFolder(fullPath)
    return true
  } catch (e) {
    log.error('[Main] storage:reveal error:', e)
    return false
  }
})
