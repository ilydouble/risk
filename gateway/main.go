package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/L1ndenbaum/stellarmesh-sdk/sdk/go/gateway"
	"github.com/redis/go-redis/v9"
)

type sessionIdentity struct {
	Version     int      `json:"version"`
	UserID      string   `json:"user_id"`
	Username    string   `json:"username"`
	DisplayName string   `json:"display_name"`
	Roles       []string `json:"roles"`
}

func sessionKey(token string) string {
	digest := sha256.Sum256([]byte(token))
	return "risk:session:v1:" + hex.EncodeToString(digest[:])
}

func sessionAuthenticator(client *redis.Client) gateway.Authenticator {
	return gateway.AuthenticatorFunc(func(ctx context.Context, token string) (gateway.AuthenticationDecision, error) {
		value, err := client.Get(ctx, sessionKey(token)).Result()
		if errors.Is(err, redis.Nil) {
			return gateway.AuthenticationDecision{Reason: "expired"}, nil
		}
		if err != nil {
			return gateway.AuthenticationDecision{}, err
		}
		var identity sessionIdentity
		if err := json.Unmarshal([]byte(value), &identity); err != nil {
			return gateway.AuthenticationDecision{}, err
		}
		if identity.Version != 1 || identity.UserID == "" {
			return gateway.AuthenticationDecision{}, errors.New("invalid stored session")
		}
		return gateway.AuthenticationDecision{
			Authenticated: true,
			Identity:      gateway.Identity{UserID: identity.UserID, Roles: identity.Roles},
		}, nil
	})
}

func errorResponder(w http.ResponseWriter, _ *http.Request, failure gateway.GatewayError) {
	code := "GATEWAY_ERROR"
	switch failure.Code {
	case "missing_credential", "invalid_credential":
		code = "AUTH_SESSION_EXPIRED"
	case "authentication_failed", "authenticator_unavailable":
		code = "AUTH_STORE_UNAVAILABLE"
	case "proxy_policy_rejected":
		code = "REQUEST_ORIGIN_INVALID"
	case "route_not_found":
		code = "ROUTE_NOT_FOUND"
	case "upstream_unavailable", "upstream_proxy_failed":
		code = "UPSTREAM_UNAVAILABLE"
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(failure.Status)
	_ = json.NewEncoder(w).Encode(struct {
		Code         int            `json:"code"`
		InternalCode string         `json:"internal_code"`
		Message      string         `json:"message"`
		Data         map[string]any `json:"data"`
	}{failure.Status, code, failure.Message, map[string]any{"field": nil, "reason": failure.Message}})
}

func newHandler(client *redis.Client, upstreamURL, allowedOrigin string) (http.Handler, error) {
	cookie, err := gateway.CookieCredential("risk_sid")
	if err != nil {
		return nil, err
	}
	return gateway.New(
		gateway.WithRoutes(
			gateway.Route{Name: "register", Match: gateway.RouteMatch{ExactPath: "/api/v1/auth/register", Methods: []string{"POST"}}, Upstream: "api", Access: gateway.AccessPublic},
			gateway.Route{Name: "login", Match: gateway.RouteMatch{ExactPath: "/api/v1/auth/login", Methods: []string{"POST"}}, Upstream: "api", Access: gateway.AccessPublic},
			gateway.Route{Name: "logout", Match: gateway.RouteMatch{ExactPath: "/api/v1/auth/logout", Methods: []string{"POST"}}, Upstream: "api", Access: gateway.AccessPublic},
			gateway.Route{Name: "business", Match: gateway.RouteMatch{PathPrefix: "/api/v1/", Methods: []string{"POST"}}, Upstream: "api"},
			gateway.Route{Name: "openapi", Match: gateway.RouteMatch{ExactPath: "/openapi.json", Methods: []string{"GET"}}, Upstream: "api", Access: gateway.AccessPublic},
		),
		gateway.WithUpstreams(gateway.Upstream{Name: "api", URL: upstreamURL}),
		gateway.WithAuthenticator(sessionAuthenticator(client), cookie),
		gateway.WithBeforeProxyPolicy(gateway.BeforeProxyPolicyFunc(func(_ context.Context, request *http.Request, _ gateway.RequestContext) (gateway.PolicyDecision, error) {
			if request.Method == http.MethodPost {
				valid := false
				for _, origin := range strings.Split(allowedOrigin, ",") {
					valid = valid || request.Header.Get("Origin") == origin
				}
				if !valid {
					return gateway.PolicyDecision{Reason: "origin"}, nil
				}
			}
			return gateway.PolicyDecision{Allowed: true}, nil
		})),
		gateway.WithErrorResponder(gateway.ErrorResponderFunc(errorResponder)),
		gateway.WithHealth(gateway.HealthConfig{
			Service: "risk-gateway",
			Readiness: gateway.ReadinessCheckerFunc(func(ctx context.Context) error {
				return client.Ping(ctx).Err()
			}),
		}),
	)
}

func env(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func main() {
	options, err := redis.ParseURL(env("REDIS_URL", "redis://localhost:6379/0"))
	if err != nil {
		slog.Error("Invalid Redis URL", "error", err)
		os.Exit(1)
	}
	client := redis.NewClient(options)
	defer client.Close()
	handler, err := newHandler(client, env("BACKEND_URL", "http://localhost:8000"), env("ALLOWED_ORIGIN", "http://localhost:18080,http://localhost:3000"))
	if err != nil {
		slog.Error("Invalid gateway configuration", "error", err)
		os.Exit(1)
	}
	server := &http.Server{Addr: ":8081", Handler: handler, ReadHeaderTimeout: 5 * time.Second}
	slog.Info("Gateway listening", "addr", server.Addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("Gateway stopped", "error", err)
		os.Exit(1)
	}
}
