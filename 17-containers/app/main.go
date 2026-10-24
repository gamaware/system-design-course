// Command web is the small HTTP service that Lab 17 packages as a container image and runs on Kubernetes.
//
// Endpoints:
//
//	/         one line: version, host name (the pod name on Kubernetes) and uptime
//	/healthz  liveness: 200 while the process can serve requests
//	/readyz   readiness: 503 for READY_DELAY seconds after start and while shutting down, 200 otherwise
//	/work     burns CPU for ?ms= milliseconds (at most 1000), used to trigger the autoscaler
//
// The binary also runs its own health check ("web -healthcheck"), because the runtime image has no shell
// and no curl for a Docker HEALTHCHECK to call.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"
)

// version is set at build time: go build -ldflags "-X main.version=v2".
var version = "dev"

func main() {
	healthcheck := flag.Bool("healthcheck", false, "call /healthz on the local server and exit 0 if it answers 200")
	flag.Parse()

	port := envOr("PORT", "8080")
	if *healthcheck {
		os.Exit(probe(port))
	}

	readyDelay, err := strconv.Atoi(envOr("READY_DELAY", "0"))
	if err != nil || readyDelay < 0 {
		log.Fatalf("READY_DELAY must be a whole number of seconds, got %q", os.Getenv("READY_DELAY"))
	}

	host, err := os.Hostname()
	if err != nil {
		host = "unknown"
	}
	started := time.Now()
	var ready, stopping atomic.Bool

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		fmt.Fprintf(w, "version=%s host=%s uptime=%ds\n", version, host, int(time.Since(started).Seconds()))
	})
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		fmt.Fprintln(w, "ok")
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, _ *http.Request) {
		if !ready.Load() || stopping.Load() {
			http.Error(w, "not ready", http.StatusServiceUnavailable)
			return
		}
		fmt.Fprintln(w, "ready")
	})
	mux.HandleFunc("/work", func(w http.ResponseWriter, r *http.Request) {
		ms, err := strconv.Atoi(r.URL.Query().Get("ms"))
		if err != nil || ms < 0 {
			ms = 50
		}
		ms = min(ms, 1000)
		deadline := time.Now().Add(time.Duration(ms) * time.Millisecond)
		n := 0
		for time.Now().Before(deadline) {
			n++
		}
		fmt.Fprintf(w, "version=%s host=%s worked=%dms loops=%d\n", version, host, ms, n)
	})

	var inFlight atomic.Int64
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           logRequests(mux, &inFlight),
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("lab17-web %s listening on :%s (host %s, ready after %ds)", version, port, host, readyDelay)
	go func() {
		time.Sleep(time.Duration(readyDelay) * time.Second)
		ready.Store(true)
		log.Printf("ready to receive traffic")
	}()

	// Kubernetes sends SIGTERM before it kills a pod; Docker sends it on "docker stop".
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	// Shutdown stops accepting connections at once, so ListenAndServe returns before the requests in
	// progress finish. main waits on this channel until Shutdown has drained them.
	drained := make(chan struct{})
	go func() {
		defer close(drained)
		<-ctx.Done()
		stopping.Store(true)
		log.Printf("SIGTERM received: finishing %d in-flight request(s)", inFlight.Load())
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			log.Printf("shutdown: %v", err)
		}
	}()

	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("server: %v", err)
	}
	<-drained
	log.Printf("stopped")
}

// logRequests counts the requests in progress and writes one line per request to stdout, which
// "docker logs" and "kubectl logs" show. Probe requests are left out of both, so that the count and
// the log show only real traffic.
func logRequests(next http.Handler, inFlight *atomic.Int64) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/healthz" || r.URL.Path == "/readyz" {
			next.ServeHTTP(w, r)
			return
		}
		inFlight.Add(1)
		defer inFlight.Add(-1)
		next.ServeHTTP(w, r)
		log.Printf("%s %s from %s", r.Method, r.URL.RequestURI(), r.RemoteAddr)
	})
}

func probe(port string) int {
	client := http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get("http://127.0.0.1:" + port + "/healthz")
	if err != nil {
		fmt.Fprintln(os.Stderr, "healthcheck:", err)
		return 1
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		fmt.Fprintln(os.Stderr, "healthcheck: status", resp.StatusCode)
		return 1
	}
	return 0
}

func envOr(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}
