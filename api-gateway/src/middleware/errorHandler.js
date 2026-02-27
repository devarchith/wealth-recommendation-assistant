'use strict';

/**
 * Global error handling middleware for the API gateway.
 */

/**
 * 404 handler — catches requests to undefined routes.
 */
function notFoundHandler(req, res) {
  res.status(404).json({
    error: `Route ${req.method} ${req.path} not found`,
    code: 'NOT_FOUND',
  });
}

/**
 * Global error handler.
 * Normalizes all thrown errors into a consistent JSON response format.
 * Hides internal details in production to prevent information leakage.
 */
function errorHandler(err, req, res, _next) {
  const isDev = process.env.NODE_ENV !== 'production';

  // CORS errors
  if (err.message && err.message.startsWith('CORS:')) {
    return res.status(403).json({ error: err.message, code: 'CORS_ERROR' });
  }

  // ML service timeout
  if (err.message && err.message.includes('timed out')) {
    return res.status(504).json({
      error: 'The AI service took too long to respond. Please try again.',
      code: 'ML_TIMEOUT',
    });
  }

  // ML service unavailable
  if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND') {
    return res.status(503).json({
      error: 'The AI service is temporarily unavailable.',
      code: 'ML_UNAVAILABLE',
    });
  }

  // Generic internal server error
  const statusCode = err.status || err.statusCode || 500;
  console.error('[error-handler]', err.message, isDev ? err.stack : '');

  return res.status(statusCode).json({
    error: isDev ? err.message : 'An unexpected error occurred.',
    code: 'INTERNAL_ERROR',
    ...(isDev && { stack: err.stack }),
  });
}

module.exports = { notFoundHandler, errorHandler };
