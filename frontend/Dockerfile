FROM node:20-alpine

WORKDIR /app

# Copy dependency files first for Docker layer caching
COPY package*.json ./

RUN npm install

# Copy application source code
COPY . .

EXPOSE 3000

# Run Next.js dev server with hot-reload
CMD ["npm", "run", "dev"]
