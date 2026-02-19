/**
 * Usage Tracker — Query limits per plan
 * Tracks daily and monthly query counts per user.
 * In production, replace the in-memory Map with Redis.
 */

'use strict';

class UsageTracker {
  constructor() {
    this._usage = new Map();
    // Reset daily counts at midnight
    this._scheduleDailyReset();
  }

  _key(userId) {
    return String(userId);
  }

  _ensureRecord(userId) {
    const key = this._key(userId);
    if (!this._usage.has(key)) {
      this._usage.set(key, {
        queries_today:       0,
        queries_this_month:  0,
        reset_at:            this._nextMidnight(),
        month_start:         this._monthStart(),
      });
    }
    return this._usage.get(key);
  }

  increment(userId) {
    const record = this._ensureRecord(userId);
    record.queries_today++;
    record.queries_this_month++;
    return record;
  }

  getUsage(userId) {
    return this._ensureRecord(userId);
  }

  resetDaily() {
    for (const record of this._usage.values()) {
      record.queries_today = 0;
      record.reset_at      = this._nextMidnight();
    }
  }

  resetMonthly() {
    for (const record of this._usage.values()) {
      record.queries_this_month = 0;
      record.month_start        = this._monthStart();
    }
  }

  _nextMidnight() {
    const d = new Date();
    d.setHours(24, 0, 0, 0);
    return d.toISOString();
  }

  _monthStart() {
    const d = new Date();
    d.setDate(1);
    d.setHours(0, 0, 0, 0);
    return d.toISOString();
  }

  _scheduleDailyReset() {
    const now      = new Date();
    const midnight = new Date();
    midnight.setHours(24, 0, 0, 0);
    const msToMidnight = midnight - now;

    setTimeout(() => {
      this.resetDaily();
      setInterval(() => this.resetDaily(), 24 * 60 * 60 * 1000).unref();
    }, msToMidnight).unref();

    // Monthly reset on 1st at midnight
    const firstOfMonth = new Date();
    firstOfMonth.setMonth(firstOfMonth.getMonth() + 1, 1);
    firstOfMonth.setHours(0, 0, 0, 0);
    const msToFirstOfMonth = firstOfMonth - now;
    setTimeout(() => {
      this.resetMonthly();
      setInterval(() => {
        const d = new Date();
        if (d.getDate() === 1 && d.getHours() === 0) this.resetMonthly();
      }, 60 * 60 * 1000).unref();
    }, msToFirstOfMonth).unref();
  }
}

const usageTracker = new UsageTracker();
module.exports = { usageTracker };
