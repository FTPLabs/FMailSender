'use strict'
/**
 * FMailSender Electron Main Process v7.3.1
 * Starts the Node.js backend then opens the BrowserWindow.
 * Replaces src-tauri/src/main.rs entirely.
 */
const { app, BrowserWindow, shell, Menu, Tray, nativeImage } = require('electron')
const path = require('path')
const { fork } = require('child_process')

// Handle Squirrel startup events (Windows installer)
if (require('electron-squirrel-startup')) app.quit()

// ── Config ────────────────────────────────────────────────────────────────────
const CORE_PORT    = 7531
const HEALTH_URL   = `http://127.0.0.1:${CORE_PORT}/api/health`
const HEALTH_TRIES = 60   // up to 30 s (60 × 500 ms)
const isDev        = !app.isPackaged

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

function startBackend() {
  const entry = getBackendEntry()
  const uiDist = getUiDist()

  _backendProc = fork(entry, [], {
    env: {
      ...process.env,
      FMAIL_PORT:    String(CORE_PORT),
      FMAIL_UI_DIST: uiDist,
      FMAIL_DATA_DIR: path.join(app.getPath('appData'), 'FMailSender'),
      NODE_ENV:      isDev ? 'development' : 'production',
    },
    silent: true,
    detached: false,
  })

  _backendProc.stdout?.on('data', d => console.log('[backend]', d.toString().trim()))
  _backendProc.stderr?.on('data', d => console.error('[backend]', d.toString().trim()))

  _backendProc.on('exit', (code, signal) => {
    console.log(`[backend] exited code=${code} signal=${signal}`)
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
          res.on('data', () => {})
          res.on('end', () => resolve())
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
    console.error('[main] Backend failed to start within 30s — opening anyway')
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
