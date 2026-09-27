FROM golang:1.25.4-bookworm AS build
WORKDIR /src
ARG GOPROXY
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -o /gateway .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /gateway /gateway
EXPOSE 8081
ENTRYPOINT ["/gateway"]
