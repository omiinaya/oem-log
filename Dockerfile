# Build oem/log and serve dist/ with the repo's dependency-free python server.
# Coolify application build pack: "dockerfile".
#   Build:   npm ci --no-audit --no-fund && npm run build
#   Start:   python3 /app/scripts/serve.py --bind 0.0.0.0 --port 80 --root /app/dist
FROM node:22-alpine AS build
WORKDIR /app
# Native deps (sharp) need libc6-compat on alpine.
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build && test -f dist/index.html

FROM python:3-alpine AS runtime
WORKDIR /app
# Static files plus the server script only.
COPY --from=build /app/dist /app/dist
COPY scripts/serve.py /app/scripts/serve.py
# Serve on 80, not 4321: Coolify's Traefik labels the backend port from the
# app's exposed port, which defaults to 80 and is not writable via the API.
# Listening on anything else yields a 502 from the proxy.
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:80/').read()" || exit 1
CMD ["python3", "/app/scripts/serve.py", "--bind", "0.0.0.0", "--port", "80", "--root", "/app/dist"]
