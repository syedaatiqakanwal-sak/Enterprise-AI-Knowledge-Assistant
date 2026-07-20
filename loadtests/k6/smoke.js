import http from "k6/http";
import { check, sleep, group } from "k6";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const EMAIL = __ENV.TEST_EMAIL || "admin@example.com";
const PASSWORD = __ENV.TEST_PASSWORD || "AdminPass123!";

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "1m", target: 20 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

export default function () {
  group("health", () => {
    const live = http.get(`${BASE}/live`);
    check(live, { "live 200": (r) => r.status === 200 });
    const ready = http.get(`${BASE}/ready`);
    check(ready, { "ready ok": (r) => r.status === 200 || r.status === 503 });
  });

  let token = null;
  group("auth", () => {
    const res = http.post(
      `${BASE}/api/v1/auth/login`,
      JSON.stringify({ email: EMAIL, password: PASSWORD }),
      { headers: { "Content-Type": "application/json" } },
    );
    check(res, { "login 200": (r) => r.status === 200 });
    if (res.status === 200) {
      const body = res.json();
      token = body?.data?.tokens?.access_token;
    }
  });

  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  group("chat", () => {
    http.get(`${BASE}/api/v1/chat/sessions`, { headers });
  });

  group("rag-search", () => {
    http.get(`${BASE}/api/v1/search?q=policy&limit=5`, { headers });
  });

  group("ocr", () => {
    http.get(`${BASE}/api/v1/ocr/jobs`, { headers });
  });

  group("meetings", () => {
    http.get(`${BASE}/api/v1/meetings`, { headers });
  });

  group("agents", () => {
    http.get(`${BASE}/api/v1/agent/sessions`, { headers });
  });

  sleep(1);
}
