'use strict';

/**
 * In-process session store for conversation history.
 *
 * Stores the last N messages per session. Designed for single-instance
 * or PM2 cluster mode (each worker has its own store; sticky sessions
 * ensure a client always hits the same worker). For multi-node deploys,
 * swap to a Redis-backed store via connect-redis.
 *
 * Capacity target: 8,000 concurrent sessions × 10 messages each at
 * ~200 bytes/message ≈ 16 MB — well within Node.js heap limits.
 */

const MAX_HISTORY_PER_SESSION = 20; // messages (10 exchanges)
const SESSION_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours

class SessionStore {
  constructor() {
    /** @type {Map<string, { messages: Array, lastAccessed: number }>} */
    this._store = new Map();

    // Periodic GC: evict sessions older than TTL every 10 minutes
    this._gcInterval = setInterval(() => this._gc(), 10 * 60 * 1000);
    if (this._gcInterval.unref) this._gcInterval.unref(); // Don't block process exit
  }

  /**
   * Append a message to the session history.
   * Drops the oldest message when the window is full.
   *
   * @param {string} sessionId
   * @param {{ role: string, content: string, timestamp: string, sources?: Array, latency_ms?: number }} message
   */
  addMessage(sessionId, message) {
    if (!this._store.has(sessionId)) {
      this._store.set(sessionId, { messages: [], lastAccessed: Date.now() });
    }
    const entry = this._store.get(sessionId);
    entry.messages.push(message);
    if (entry.messages.length > MAX_HISTORY_PER_SESSION) {
      entry.messages.shift(); // remove oldest
    }
    entry.lastAccessed = Date.now();
  }

  /**
   * Return all stored messages for a session (oldest first).
   * @param {string} sessionId
   * @returns {Array}
   */
  getHistory(sessionId) {
    const entry = this._store.get(sessionId);
    if (!entry) return [];
    entry.lastAccessed = Date.now();
    return [...entry.messages];
  }

  /**
   * Remove all messages for a session.
   * @param {string} sessionId
   * @returns {boolean} true if the session existed
   */
  clearSession(sessionId) {
    return this._store.delete(sessionId);
  }

  /**
   * Return the number of active sessions.
   */
  size() {
    return this._store.size;
  }

  /**
   * Internal GC: evict sessions not accessed within SESSION_TTL_MS.
   */
  _gc() {
    const now = Date.now();
    let evicted = 0;
    for (const [id, entry] of this._store.entries()) {
      if (now - entry.lastAccessed > SESSION_TTL_MS) {
        this._store.delete(id);
        evicted++;
      }
    }
    if (evicted > 0) {
      console.log(`[session-store] GC evicted ${evicted} stale sessions`);
    }
  }
}

// Singleton — shared across all route handlers in the same process
const sessionStore = new SessionStore();

module.exports = { sessionStore, SessionStore };
