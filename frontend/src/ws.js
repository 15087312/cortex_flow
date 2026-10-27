import { reactive } from 'vue'

class WebSocketManager {
  constructor() {
    this.ws = null
    this.listeners = []
    this.reconnectTimer = null
    this.reconnectDelay = 1000
    this.state = reactive({ connected: false })
  }

  connect() {
    if (this.ws && this.ws.readyState <= 1) return
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.ws = new WebSocket(`${protocol}//${location.host}/api/events`)

    this.ws.onopen = () => {
      this.state.connected = true
      this.reconnectDelay = 1000
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.listeners.forEach(cb => cb(data))
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    this.ws.onclose = () => {
      this.state.connected = false
      this._scheduleReconnect()
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelay)
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 5000)
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
    this.state.connected = false
  }

  onEvent(callback) {
    this.listeners.push(callback)
  }

  offEvent(callback) {
    this.listeners = this.listeners.filter(cb => cb !== callback)
  }

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsManager = new WebSocketManager()
