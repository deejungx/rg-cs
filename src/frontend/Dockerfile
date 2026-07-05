FROM node:20-alpine

WORKDIR /app

COPY src/frontend/package.json ./
RUN npm install

COPY src/frontend/ ./

EXPOSE 8080

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8080"]
