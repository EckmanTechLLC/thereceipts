/**
 * WebSocket client for real-time pipeline progress updates.
 *
 * Manages WebSocket connection lifecycle and event handling.
 */

export type ProgressEvent =
  | { type: 'pipeline_started'; timestamp: string; question: string }
  | { type: 'agent_started'; timestamp: string; agent_name: string }
  | { type: 'agent_completed'; timestamp: string; agent_name: string; duration: number; success: boolean }
  | { type: 'pipeline_completed'; timestamp: string; duration: number }
  | { type: 'pipeline_failed'; timestamp: string; error: string; duration: number }
  | { type: 'pong'; timestamp: string };

export type ProgressEventHandler = (event: ProgressEvent) => void;

export class PipelineWebSocketClient {
  private ws: WebSocket | null = null;
  private _sessionId: string;
  private url: string;
  private eventHandlers: ProgressEventHandler[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private reconnectDelay = 1000; // ms
  private isManualClose = false;
  private pingInterval: number | null = null;

  constructor(sessionId: string) {
    this._sessionId = sessionId;
    // Determine WebSocket URL based on current environment
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_WS_URL || window.location.host;
    this.url = `${protocol}//${host}/ws/pipeline/${sessionId}`;
  }

  /**
   * Connect to the WebSocket server.
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        this.isManualClose = false;

        this.ws.onopen = () => {
          console.log(`[WebSocket] Connected to ${this.url}`);
          this.reconnectAttempts = 0;
          this.startPingInterval();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ProgressEvent;
            this.handleEvent(data);
          } catch (error) {
            console.error('[WebSocket] Failed to parse message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log('[WebSocket] Closed:', event.code, event.reason);
          this.stopPingInterval();

          // Attempt reconnection if not a manual close
          if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] Reconnecting (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => {
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Add an event handler for progress events.
   */
  onProgress(handler: ProgressEventHandler): void {
    this.eventHandlers.push(handler);
  }

  /**
   * Remove an event handler.
   */
  offProgress(handler: ProgressEventHandler): void {
    this.eventHandlers = this.eventHandlers.filter(h => h !== handler);
  }

  /**
   * Close the WebSocket connection.
   */
  close(): void {
    this.isManualClose = true;
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Check if the WebSocket is connected.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Send a ping message to keep connection alive.
   */
  private ping(): void {
    if (this.isConnected() && this.ws) {
      this.ws.send('ping');
    }
  }

  /**
   * Start sending periodic ping messages.
   */
  private startPingInterval(): void {
    this.pingInterval = window.setInterval(() => {
      this.ping();
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop sending ping messages.
   */
  private stopPingInterval(): void {
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Handle incoming progress events.
   */
  private handleEvent(event: ProgressEvent): void {
    this.eventHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('[WebSocket] Event handler error:', error);
      }
    });
  }
}
