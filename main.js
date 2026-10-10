/**
 * Main entry point for the Career Guidance System
 */

import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Health check endpoint
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', message: 'Career Guidance System is running' });
});

// Placeholder routes
app.get('/', (_req, res) => {
  res.json({ message: 'Welcome to the Career Guidance System API' });
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

export default app;