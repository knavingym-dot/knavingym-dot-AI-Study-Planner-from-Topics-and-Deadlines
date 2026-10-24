import express from 'express';
import { createServer as createViteServer } from 'vite';
import http from 'http';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const PYTHON_PORT = 5000;

let pythonProcess: ChildProcess | null = null;
let isShuttingDown = false;

function startPythonBackend() {
  if (isShuttingDown) return;
  if (pythonProcess && !pythonProcess.killed) return;

  const pythonEnv = {
    ...process.env,
    STUDYFLOW_PORT: String(PYTHON_PORT),
    STUDYFLOW_HOST: '127.0.0.1',
  };

  const proc = spawn('python3', ['server.py'], {
    cwd: __dirname,
    env: pythonEnv,
    stdio: ['ignore', 'inherit', 'inherit'],
  });

  proc.on('error', (err) => {
    console.error('Failed to start python backend:', err);
  });

  proc.on('exit', (code, signal) => {
    if (!isShuttingDown) {
      console.log(`Python backend exited (code ${code}, signal ${signal}). Restarting in 1s...`);
      pythonProcess = null;
      setTimeout(startPythonBackend, 1000);
    }
  });

  pythonProcess = proc;
}

startPythonBackend();

process.on('SIGINT', () => {
  isShuttingDown = true;
  if (pythonProcess) pythonProcess.kill('SIGINT');
  process.exit(0);
});

process.on('SIGTERM', () => {
  isShuttingDown = true;
  if (pythonProcess) pythonProcess.kill('SIGTERM');
  process.exit(0);
});

async function main() {
  const app = express();

  // Route API requests to Python backend
  app.use('/api', (req, res) => {
    const proxyOptions: http.RequestOptions = {
      hostname: '127.0.0.1',
      port: PYTHON_PORT,
      path: req.originalUrl,
      method: req.method,
      headers: {
        ...req.headers,
        host: `127.0.0.1:${PYTHON_PORT}`,
      },
    };

    const proxyReq = http.request(proxyOptions, (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 500, proxyRes.headers);
      proxyRes.pipe(res);
    });

    proxyReq.on('error', (_err) => {
      if (!res.headersSent) {
        res.status(503).json({ error: 'Backend server is starting up. Please retry in a moment.' });
      }
    });

    req.pipe(proxyReq);
  });

  // Serve static files or Vite middlewares
  const isProduction = process.env.NODE_ENV === 'production';

  if (!isProduction) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Studyflow server is ready on http://0.0.0.0:${PORT}`);
  });
}

main().catch((err) => {
  console.error('Error starting server:', err);
  process.exit(1);
});
