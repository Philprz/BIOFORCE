const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8080;
const MIME_TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

const server = http.createServer((req, res) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
  
  // Handle API mock endpoints for testing
  if (req.url.startsWith('/api/')) {
    res.setHeader('Content-Type', 'application/json');
    
    // Simulate various API endpoints with mock data
    if (req.url === '/api/system/info') {
      res.end(JSON.stringify({
        version: '1.0.0',
        python_version: '3.9.7',
        platform: 'Windows',
        current_time: new Date().toISOString(),
        github_repo: 'https://github.com/Philprz/BIOFORCE'
      }));
      return;
    }
    
    if (req.url === '/api/system/status') {
      res.end(JSON.stringify({
        server_status: 'ok',
        scraping_status: 'ready',
        qdrant_status: 'connected',
      }));
      return;
    }
    
    if (req.url === '/api/qdrant/stats') {
      res.end(JSON.stringify({
        'faq_collection': {
          vectors_count: 120,
          segments_count: 2,
          ram_usage: 5242880  // 5 MB
        },
        'full_site_collection': {
          vectors_count: 450,
          segments_count: 4,
          ram_usage: 10485760  // 10 MB
        }
      }));
      return;
    }
    
    // Default response for unknown API endpoints
    res.statusCode = 404;
    res.end(JSON.stringify({ error: 'API endpoint not found' }));
    return;
  }
  
  // Handle file serving
  let filePath = '.' + req.url;
  if (filePath === './') {
    filePath = './bioforce-admin/index.html';
  } else if (filePath === './bioforcebot') {
    // Create a simple test page for bioforcebot
    res.setHeader('Content-Type', 'text/html');
    res.end(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>BioforceBot Test</title>
          <script src="bioforcebot.js"></script>
        </head>
        <body>
          <h1>BioforceBot Test</h1>
          <div id="bioforcebot-container"></div>
          <script>
            document.addEventListener('DOMContentLoaded', () => {
              const bot = new BioforceBot();
              bot.init('bioforcebot-container');
            });
          </script>
        </body>
      </html>
    `);
    return;
  }
  
  const extname = path.extname(filePath);
  let contentType = MIME_TYPES[extname] || 'application/octet-stream';
  
  fs.readFile(filePath, (error, content) => {
    if (error) {
      if (error.code === 'ENOENT') {
        console.error(`File not found: ${filePath}`);
        res.writeHead(404);
        res.end('File not found');
      } else {
        console.error(`Server error: ${error.code}`);
        res.writeHead(500);
        res.end(`Server Error: ${error.code}`);
      }
    } else {
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content, 'utf-8');
    }
  });
});

server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}/`);
  console.log(`BioforceBot demo at http://localhost:${PORT}/bioforcebot`);
  console.log(`Admin interface at http://localhost:${PORT}/bioforce-admin/index.html`);
});
