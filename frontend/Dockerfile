# Railway deploy - builds from repo root context
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files (paths from repo root)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY frontend/. .

# Build arguments for environment variables (needed at build time for Next.js)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL

# Convert ARGs to ENVs so Next.js can read them during build
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

# Build the application
RUN npm run build

# Production stage
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy standalone build output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 3000

# Set hostname for container
ENV HOSTNAME="0.0.0.0"

# Run the application
CMD ["node", "server.js"]
