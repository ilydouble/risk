package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"slices"
	"strconv"
	"testing"

	"github.com/L1ndenbaum/stellarmesh-sdk/sdk/go/gateway"
)

func TestRequestIDProxyCorrelation(t *testing.T) {
	for _, incoming := range []struct {
		name       string
		values     []string
		connection string
	}{
		{name: "missing"},
		{name: "client", values: []string{"client-id"}},
		{name: "duplicate", values: []string{"client-id", "another-client-id"}},
		{name: "connection", values: []string{"client-id"}, connection: "keep-alive, X-Request-ID"},
	} {
		for _, reply := range []string{"missing", "echo", "different", "duplicate"} {
			for _, status := range []int{http.StatusOK, http.StatusUnprocessableEntity, http.StatusInternalServerError} {
				t.Run(incoming.name+"/"+reply+"/"+strconv.Itoa(status), func(t *testing.T) {
					forwarded := make(chan []string, 1)
					upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						forwarded <- r.Header.Values(requestIDHeader)
						switch reply {
						case "echo":
							w.Header().Set(requestIDHeader, r.Header.Get(requestIDHeader))
						case "different":
							w.Header().Set(requestIDHeader, "backend-id")
						case "duplicate":
							w.Header().Add(requestIDHeader, r.Header.Get(requestIDHeader))
							w.Header().Add(requestIDHeader, "backend-id")
						}
						w.Header().Set("Content-Type", "application/json")
						w.WriteHeader(status)
						_, _ = io.WriteString(w, `{"source":"upstream"}`)
					}))
					t.Cleanup(upstream.Close)
					var selected string
					var logged gateway.AccessLog
					handler, err := gateway.New(
						gateway.WithRoutes(gateway.Route{
							Name: "public", Match: gateway.RouteMatch{ExactPath: "/public"},
							Upstream: "api", Access: gateway.AccessPublic,
						}),
						gateway.WithUpstreams(gateway.Upstream{Name: "api", URL: upstream.URL}),
						gateway.WithBeforeProxyPolicy(gateway.BeforeProxyPolicyFunc(func(ctx context.Context, r *http.Request, request gateway.RequestContext) (gateway.PolicyDecision, error) {
							var ok bool
							selected, ok = gateway.RequestIDFromContext(ctx)
							if !ok || selected == "" || request.RequestID != selected || r.Header.Get(requestIDHeader) != selected {
								t.Errorf("request ID differs from gateway context: %q, %+v", selected, request)
							}
							return gateway.PolicyDecision{Allowed: true}, nil
						})),
						gateway.WithAccessLogger(gateway.AccessLoggerFunc(func(_ context.Context, entry gateway.AccessLog) error {
							logged = entry
							return nil
						})),
					)
					if err != nil {
						t.Fatal(err)
					}
					request := httptest.NewRequest(http.MethodGet, "/public", nil)
					for _, value := range incoming.values {
						request.Header.Add(requestIDHeader, value)
					}
					if incoming.connection != "" {
						request.Header.Set("Connection", incoming.connection)
					}
					response := httptest.NewRecorder()
					handler.ServeHTTP(response, request)
					if response.Code != status || response.Body.String() != `{"source":"upstream"}` {
						t.Fatalf("upstream response changed: %d %s", response.Code, response.Body.String())
					}
					if slices.Contains(incoming.values, selected) || selected == "" {
						t.Fatalf("client controlled the selected ID: %q", selected)
					}
					if got := <-forwarded; !slices.Equal(got, []string{selected}) {
						t.Errorf("forwarded request IDs = %v, want [%s]", got, selected)
					}
					if got := response.Result().Header.Values(requestIDHeader); !slices.Equal(got, []string{selected}) {
						t.Errorf("client response IDs = %v, want [%s]", got, selected)
					}
					if logged.RequestID != selected || logged.Status != status {
						t.Errorf("access log = %+v, want ID %s and status %d", logged, selected, status)
					}
				})
			}
		}
	}
}

func captureRequestIDLogs(t *testing.T) func() string {
	t.Helper()
	previous := slog.Default()
	var stream bytes.Buffer
	slog.SetDefault(slog.New(slog.NewJSONHandler(&stream, nil)))
	t.Cleanup(func() { slog.SetDefault(previous) })
	return func() string {
		t.Helper()
		decoder := json.NewDecoder(&stream)
		var ids []string
		for {
			var entry struct {
				Message   string `json:"msg"`
				RequestID string `json:"request_id"`
			}
			if err := decoder.Decode(&entry); err == io.EOF {
				break
			} else if err != nil {
				t.Fatal(err)
			}
			if entry.Message == "gateway request completed" {
				ids = append(ids, entry.RequestID)
			}
		}
		if len(ids) != 1 || ids[0] == "" {
			t.Fatalf("access log request IDs = %v", ids)
		}
		return ids[0]
	}
}

func TestGatewayUpstreamFailureRequestID(t *testing.T) {
	loggedID := captureRequestIDLogs(t)
	upstream := httptest.NewServer(http.NotFoundHandler())
	upstream.Close()
	handler, err := newHandler(nil, upstream.URL, "http://localhost:18080")
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodGet, "/openapi.json", nil)
	request.Header.Set(requestIDHeader, "client-id")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	var body struct {
		Code         int    `json:"code"`
		InternalCode string `json:"internal_code"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Code != response.Code || body.InternalCode != "UPSTREAM_UNAVAILABLE" {
		t.Fatalf("unexpected error envelope: %+v", body)
	}
	if ids := response.Result().Header.Values(requestIDHeader); len(ids) != 1 || ids[0] == "client-id" || ids[0] != loggedID() {
		t.Fatalf("failure response IDs = %v", ids)
	}
}
