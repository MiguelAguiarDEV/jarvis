FROM golang:1.23-alpine AS builder
RUN apk add --no-cache git
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/ cmd/
COPY internal/ internal/
RUN CGO_ENABLED=0 go build -o jarvis-bot ./cmd/bot

FROM alpine:3.21
RUN apk add --no-cache ca-certificates docker-cli
WORKDIR /app
COPY --from=builder /app/jarvis-bot /usr/local/bin/jarvis-bot
ENTRYPOINT ["jarvis-bot"]
