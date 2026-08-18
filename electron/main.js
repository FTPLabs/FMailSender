'use strict'
/**
 * FMailSender Electron Main Process v7.5.5
 * Starts the Node.js backend then opens the BrowserWindow.
 * Replaces src-tauri/src/main.rs entirely.
 */
const { app, BrowserWindow, shell, Menu, Tray, nativeImage, dialog, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')

// Handle Squirrel startup events (Windows installer)
if (require('electron-squirrel-startup')) app.quit()

// ── Config ────────────────────────────────────────────────────────────────────
const CORE_PORT    = 7531
const HEALTH_URL   = `http://127.0.0.1:${CORE_PORT}/api/health`
const HEALTH_TRIES = 60   // up to 30 s (60 × 500 ms)
const isDev        = !app.isPackaged
const hasSingleInstance = app.requestSingleInstanceLock()
if (!hasSingleInstance) app.quit()

// ── Resolve paths ─────────────────────────────────────────────────────────────
function getResourcesDir() {
  return isDev
    ? path.join(__dirname, '..')        // dev: monorepo root
    : process.resourcesPath             // packaged: resources/
}

function getBackendEntry() {
  const base = getResourcesDir()
  return isDev
    ? path.join(base, 'backend', 'src', 'server.js')
    : path.join(base, 'backend',  'src', 'server.js')
}

function getUiDist() {
  const base = getResourcesDir()
  return isDev
    ? path.join(base, 'ui', 'dist')
    : path.join(base, 'ui', 'dist')
}

// ── Backend process ───────────────────────────────────────────────────────────
let _backendProc = null

function coreLog(message) {
  try {
    const logPath = path.join(app.getPath('userData'), 'core.log')
    fs.appendFileSync(logPath, `[${new Date().toISOString()}] ${message}\n`, 'utf8')
  } catch {}
}

ipcMain.handle('app:restart', () => {
  coreLog('application relaunch requested by user')
  app.relaunch()
  app.exit(0)
  return true
})

function startBackend() {
  const entry = getBackendEntry()
  const uiDist = getUiDist()
  if (!fs.existsSync(entry)) throw new Error(`Backend entry missing: ${entry}`)
  if (!fs.existsSync(uiDist)) throw new Error(`UI assets missing: ${uiDist}`)

  // In a packaged Electron app, fork() can relaunch the GUI executable rather
  // than a Node child. Explicit ELECTRON_RUN_AS_NODE makes the backend mode
  // deterministic on Windows, while process.execPath stays portable.
  coreLog(`starting backend entry=${entry} ui=${uiDist}`)
  _backendProc = spawn(process.execPath, [entry], {
    cwd: path.dirname(entry),
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: '1',
      FMAIL_PORT:    String(CORE_PORT),
      FMAIL_UI_DIST: uiDist,
      FMAIL_DATA_DIR: path.join(app.getPath('appData'), 'FMailSender'),
      NODE_ENV:      isDev ? 'development' : 'production',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    detached: false,
  })

  _backendProc.on('error', err => {
    console.error('[backend] spawn error:', err.message)
    coreLog(`backend spawn error: ${err.message}`)
  })
  _backendProc.stdout?.on('data', d => {
    const message = d.toString().trim()
    console.log('[backend]', message)
    if (message) coreLog(`[stdout] ${message}`)
  })
  _backendProc.stderr?.on('data', d => {
    const message = d.toString().trim()
    console.error('[backend]', message)
    if (message) coreLog(`[stderr] ${message}`)
  })
  _backendProc.on('exit', (code, signal) => {
    console.log(`[backend] exited code=${code} signal=${signal}`)
    coreLog(`backend exited code=${code} signal=${signal}`)
    _backendProc = null
  })
}

function stopBackend() {
  if (_backendProc) {
    try { _backendProc.kill('SIGTERM') } catch {}
    _backendProc = null
  }
}

// ── Health check ──────────────────────────────────────────────────────────────
async function waitForBackend() {
  const http = require('http')
  for (let i = 0; i < HEALTH_TRIES; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(HEALTH_URL, res => {
          let body = ''
          res.setEncoding('utf8')
          res.on('data', chunk => { body += chunk })
          res.on('end', () => {
            try {
              const payload = JSON.parse(body)
              if (res.statusCode !== 200 || payload.ok !== true) {
                return reject(new Error(`health status ${res.statusCode}`))
              }
              resolve()
            } catch (err) {
              reject(err)
            }
          })
        })
        req.on('error', reject)
        req.setTimeout(1000, () => { req.destroy(); reject(new Error('timeout')) })
      })
      return true
    } catch {
      await new Promise(r => setTimeout(r, 500))
    }
  }
  return false
}

// ── Window ────────────────────────────────────────────────────────────────────
let _win  = null
let _tray = null

function createWindow() {
  _win = new BrowserWindow({
    width:  1280,
    height: 800,
    minWidth:  1024,
    minHeight: 640,
    show: false,  // show after ready-to-show
    backgroundColor: '#0f1117',
    title: 'FMailSender',
    autoHideMenuBar: true,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          true,
      webSecurity:      true,
    },
    icon: path.join(__dirname, 'assets', 'icon.ico'),
  })

  // Remove default menu in production
  if (!isDev) Menu.setApplicationMenu(null)

  _win.loadURL(`http://127.0.0.1:${CORE_PORT}`)

  _win.once('ready-to-show', () => {
    _win.show()
    if (isDev) _win.webContents.openDevTools()
  })

  // Open external links in browser, not Electron window
  _win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url)
    return { action: 'deny' }
  })

  _win.on('closed', () => { _win = null })
}

function createTray() {
  try {
    const iconPath = path.join(__dirname, 'assets', 'icon.ico')
    const img = nativeImage.createFromPath(iconPath)
    if (img.isEmpty()) return
    _tray = new Tray(img.resize({ width: 16, height: 16 }))
    _tray.setToolTip('FMailSender')
    const menu = Menu.buildFromTemplate([
      { label: 'Открыть FMailSender', click: () => { _win?.show() } },
      { type: 'separator' },
      { label: 'Выход', click: () => app.quit() },
    ])
    _tray.setContextMenu(menu)
    _tray.on('double-click', () => { _win?.show() })
  } catch (e) {
    console.log('[tray] failed to create tray:', e.message)
  }
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.on('ready', async () => {
  startBackend()
  const ok = await waitForBackend()
  if (!ok) {
    const message = `Ядро FMailSender не запустилось на порту ${CORE_PORT}.`
    console.error(`[main] ${message}`)
    coreLog(message)
    dialog.showErrorBox('Ошибка запуска ядра', `${message}\nЛог: %APPDATA%\\FMailSender\\core.log`)
    app.quit()
    return
  }
  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  // Keep running in tray on Windows/Linux
  if (process.platform === 'darwin') app.quit()
})

app.on('activate', () => {
  if (!_win) createWindow()
})

app.on('before-quit', () => {
  stopBackend()
})

app.on('will-quit', () => {
  stopBackend()
})
