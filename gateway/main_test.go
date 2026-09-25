package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestGatewaySessionAndEnvelope(t *testing.T) {
	store := miniredis.RunT(t)
	client := redis.NewClient(&redis.Options{Addr: store.Addr()})
	defer client.Close()
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-User-ID") != "demo-user" {
			t.Errorf("untrusted identity reached upstream: %q", r.Header.Get("X-User-ID"))
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"code":200,"internal_code":"SUCCESS","message":"OK","data":{}}`))
	}))
	defer upstream.Close()
	handler, err := newHandler(client, upstream.URL, "http://localhost:18080")
	if err != nil {
		t.Fatal(err)
	}
	call := func(origin, cookie string) (int, string) {
		t.Helper()
		request := httptest.NewRequest(http.MethodPost, "/api/v1/company/search", nil)
		request.Header.Set("Origin", origin)
		request.Header.Set("X-User-ID", "forged")
		if cookie != "" {
			request.AddCookie(&http.Cookie{Name: "risk_sid", Value: cookie})
		}
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, request)
		var body struct {
			Code         int    `json:"code"`
			InternalCode string `json:"internal_code"`
		}
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if body.Code != response.Code {
			t.Fatalf("envelope code %d != HTTP %d", body.Code, response.Code)
		}
		if response.Header().Get("X-Request-ID") == "" {
			t.Fatal("missing request ID")
		}
		return response.Code, body.InternalCode
	}
	if status, code := call("http://localhost:18080", ""); status != 401 || code != "AUTH_SESSION_EXPIRED" {
		t.Fatalf("missing session: %d %s", status, code)
	}
	store.Set(sessionKey("valid"), `{"version":1,"user_id":"demo-user","username":"demo","display_name":"Demo","roles":["demo"]}`)
	if status, code := call("http://localhost:18080", "valid"); status != 200 || code != "SUCCESS" {
		t.Fatalf("valid session: %d %s", status, code)
	}
	if status, code := call("http://evil.example", "valid"); status != 403 || code != "REQUEST_ORIGIN_INVALID" {
		t.Fatalf("invalid origin: %d %s", status, code)
	}
	store.Close()
	if status, code := call("http://localhost:18080", "valid"); status != 503 || code != "AUTH_STORE_UNAVAILABLE" {
		t.Fatalf("Redis failure: %d %s", status, code)
	}
}
