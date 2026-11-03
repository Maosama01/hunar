import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import { App } from "./App";
import { apiUrl } from "./api";
import { enableServerTtsIfConfigured } from "./tts";
import "./styles.css";

// Service worker: precaches the app shell so the app opens offline after the first visit.
registerSW({ immediate: true });

// Read-aloud with Bhashini voices when the server has Bhashini keys; device voices otherwise.
enableServerTtsIfConfigured(apiUrl("/api/health"), apiUrl("/api/tts"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
