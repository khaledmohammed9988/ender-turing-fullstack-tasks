// Test-only read-only gateway: the temporary public URL must never expose Ghost setup/admin.
const http = require("node:http")
http.createServer((req, res) => {
  let path
  try {
    path = new URL(req.url, "http://smoke.invalid").pathname
    for (let n = 0; n < 3; n++) path = decodeURIComponent(path)
  } catch {
    res.writeHead(400).end("Invalid path")
    return
  }
  if (!["GET", "HEAD"].includes(req.method) || !(
    path === "/" || path === "/favicon.ico" || path === "/robots.txt" ||
    path.startsWith("/assets/") || path.startsWith("/content/")
  ) || path.includes("..") || path.includes("\\")) {
    res.writeHead(403, { "Content-Type": "text/plain" }).end("Read-only smoke preview")
    return
  }
  const upstream = http.request({
    hostname: "ghost", port: 2368, path: req.url, method: req.method,
    headers: { ...req.headers, "x-forwarded-proto": "https" },
  }, (response) => {
    res.writeHead(response.statusCode, response.headers)
    response.pipe(res)
  })
  upstream.on("error", () => { if (!res.headersSent) res.writeHead(502); res.end("Origin unavailable") })
  req.pipe(upstream)
}).listen(8080, "0.0.0.0")
