package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestReportTransportAllowsLongAnalysisWithoutChangingOtherRoutes(t *testing.T) {
	configured := upstreamTransport().(reportTimeoutTransport)
	if got := configured.report.(*http.Transport).ResponseHeaderTimeout; got != 5*time.Minute {
		t.Fatalf("report response header timeout = %s, want 5m", got)
	}
	if got := configured.normal.(*http.Transport).ResponseHeaderTimeout; got != 30*time.Second {
		t.Fatalf("regular response header timeout = %s, want 30s", got)
	}
	configured.normal.(*http.Transport).CloseIdleConnections()
	configured.report.(*http.Transport).CloseIdleConnections()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		time.Sleep(35 * time.Millisecond)
		_, _ = io.WriteString(w, "ok")
	}))
	defer server.Close()

	normal := http.DefaultTransport.(*http.Transport).Clone()
	normal.ResponseHeaderTimeout = 10 * time.Millisecond
	report := normal.Clone()
	report.ResponseHeaderTimeout = 100 * time.Millisecond
	transport := reportTimeoutTransport{normal: normal, report: report}
	defer normal.CloseIdleConnections()
	defer report.CloseIdleConnections()

	request, err := http.NewRequest(http.MethodPost, server.URL+"/api/v1/data-prep/suggest-mapping", nil)
	if err != nil {
		t.Fatal(err)
	}
	response, err := transport.RoundTrip(request)
	if err != nil {
		t.Fatalf("report route timed out: %v", err)
	}
	_ = response.Body.Close()

	request, err = http.NewRequest(http.MethodPost, server.URL+"/api/v1/chat/complete", nil)
	if err != nil {
		t.Fatal(err)
	}
	response, err = transport.RoundTrip(request)
	if err == nil {
		_ = response.Body.Close()
		t.Fatal("regular route should keep its short response timeout")
	}
}
