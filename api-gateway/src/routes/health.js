'use strict';

const express = require('express');
const router = express.Router();
const { sessionStore } = require('../services/sessionStore');

router.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'api-gateway',
    timestamp: new Date().toISOString(),
    activeSessions: sessionStore.size(),
  });
});

module.exports = router;
